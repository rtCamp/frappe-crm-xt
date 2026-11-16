"""Pipeline becomes a Link to CRM Pipeline; CSM pipelines get their own Slack alerts.

1. Seed CRM Pipeline and map the old free-text `custom_pipeline` values onto it.
2. Keep the three existing sales alerts off CSM deals, and add a "(CSM)" copy of each that
   posts to the CSM webhook for CSM deals only. Copies are created disabled, like the originals.
"""

import frappe
from frappe.query_builder.functions import Count
from pypika.functions import Cast, Trim

CSM_WEBHOOK = "CRM CSM"
SUFFIX = " (CSM)"

# old text value (lowercase) -> pipeline. Anything not listed keeps its trimmed value as its own pipeline.
MAP = {
	"inbound pipeline": "Inbound",
	"renewals": "Renewals",
	"renewal": "Renewals",
	"existing accounts & renewals": "Renewals",
	"existing accounts & renewal": "Renewals",
	"existing clients & renewals": "Renewals",
	"easy engine": "EasyEngine",
	"erpnext": "ERPNext/Frappe",
}
# CSM deals are the ones whose pipeline contains this word. It is written into the Notification
# conditions below; change it there (desk) afterwards.
CSM_KEYWORD = "renewal"

DEAL_PIPELINE = "(doc.custom_pipeline or '').lower()"
NOTE_DEAL_PIPELINE = (
	'(frappe.db.get_value("CRM Deal", doc.reference_docname, "custom_pipeline") or "").lower()'
)

# notification -> (expression for the deal's pipeline, copy keeps the original condition?)
ALERTS = {
	"CRM Slack — CRM Deal Updates": (DEAL_PIPELINE, True),
	"CRM Slack — CRM Deal Note Added": (NOTE_DEAL_PIPELINE, True),
	"CRM Slack — CRM Deal Inactivity (7 days)": (
		DEAL_PIPELINE,
		False,
	),  # old `'renewal' not in (doc.custom_pipeline or '').lower()` is replaced
}


def execute():
	# Frappe refuses Data -> Link on a Custom Field, so flip it here; custom_fields.json then matches.
	frappe.db.set_value(
		"Custom Field",
		"CRM Deal-custom_pipeline",
		{"fieldtype": "Link", "options": "CRM Pipeline"},
		update_modified=False,
	)
	frappe.clear_cache(doctype="CRM Deal")
	migrate_pipelines()
	split_notifications()


def migrate_pipelines():
	"""Every distinct deal value (trimmed) becomes a CRM Pipeline, and deals are pointed at its exact name.

	Trimmed + case-insensitive on purpose: MariaDB compares 'X ' = 'X' = 'x', so a plain `distinct`
	would hide variants. Raises if any deal is left without a matching pipeline.
	"""
	deal = frappe.qb.DocType("CRM Deal")
	trimmed = Trim(deal.custom_pipeline)
	# '' or whitespace-only -> NULL, so "no pipeline" has one representation
	(
		frappe.qb.update(deal)
		.set(deal.custom_pipeline, None)
		.where(deal.custom_pipeline.isnotnull())
		.where(trimmed == "")
	).run()
	for (old,) in frappe.qb.from_(deal).select(trimmed).distinct().where(trimmed != "").run():
		new = MAP.get(old.lower(), old)
		if not frappe.db.exists("CRM Pipeline", new):
			frappe.get_doc({"doctype": "CRM Pipeline", "pipeline_name": new}).insert(ignore_permissions=True)
		new = frappe.db.get_value("CRM Pipeline", new, "name")  # canonical spelling of an existing row
		# direct update: touching `modified` would fire "Deal updated" for every deal
		(
			frappe.qb.update(deal)
			.set(deal.custom_pipeline, new)
			.where(trimmed == old)
			.where(deal.custom_pipeline != Cast(new, "BINARY"))  # byte compare, so case/space variants differ
		).run()
	pipeline = frappe.qb.DocType("CRM Pipeline")
	orphans = (
		frappe.qb.from_(deal)
		.left_join(pipeline)
		.on(pipeline.name == Cast(deal.custom_pipeline, "BINARY"))
		.select(Count("*"))
		.where(deal.custom_pipeline != "")
		.where(pipeline.name.isnull())
	).run()[0][0]
	if orphans:
		frappe.throw(f"{orphans} CRM Deal(s) still have a pipeline missing from CRM Pipeline")


def split_notifications():
	webhook = CSM_WEBHOOK if frappe.db.exists("Slack Webhook URL", CSM_WEBHOOK) else None
	for name, (pipeline, keep_condition) in ALERTS.items():
		if not frappe.db.exists("Notification", name):
			continue
		sales = frappe.get_doc("Notification", name)
		if sales.condition_type == "Filters":
			if sales.filters:
				# Filters and the Python routing check can't be combined in one Notification
				frappe.throw(f"Convert {name!r} to a Python condition first, then re-run migrate")
			sales.condition_type = "Python"  # no filters set: Filters mode would ignore the routing check
		old = sales.condition or ""
		is_csm, not_csm = f"'{CSM_KEYWORD}' in {pipeline}", f"'{CSM_KEYWORD}' not in {pipeline}"
		# the sales alert's own condition, without the routing check (also when re-running)
		if old == not_csm:
			own = ""
		elif old.endswith(f" and {not_csm}"):
			own = old.removesuffix(f" and {not_csm}")
		else:
			own = f"({old})" if old else ""
		base = f"{own} and " if own else ""
		# only the old renewal rule (or none) is replaced; any other condition is kept in both channels
		keep_condition = keep_condition or old not in ("", not_csm)
		csm_name = name + SUFFIX
		if not frappe.db.exists("Notification", csm_name):
			csm = frappe.copy_doc(sales)
			csm.name = csm_name
			csm.condition = (base if keep_condition else "") + is_csm
			csm.slack_webhook_url = webhook
			csm.enabled = 0
			csm.insert(ignore_permissions=True)
		if not_csm not in old:
			sales.condition = (base if keep_condition else "") + not_csm
			sales.save(ignore_permissions=True)

	inactivity = "CRM Slack — CRM Deal Inactivity (7 days)" + SUFFIX
	if frappe.db.exists("Notification", inactivity) and not frappe.db.get_single_value(
		"CRM XT Settings", "deal_inactivity_csm_notification"
	):  # don't undo an admin clearing it
		frappe.db.set_single_value("CRM XT Settings", "deal_inactivity_csm_notification", inactivity)
