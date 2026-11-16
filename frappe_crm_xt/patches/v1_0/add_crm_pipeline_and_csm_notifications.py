"""Pipeline becomes a Link to CRM Pipeline; CSM pipelines get their own Slack alerts.

1. Seed CRM Pipeline and map the old free-text `custom_pipeline` values onto it.
2. Keep the three existing sales alerts off CSM deals, and add a "(CSM)" copy of each that
   posts to the CSM webhook for CSM deals only. Copies are created disabled, like the originals.
"""

import frappe
from pypika.functions import Trim

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

# notification -> expression for the deal's pipeline
ALERTS = {
	"CRM Slack — CRM Deal Updates": DEAL_PIPELINE,
	"CRM Slack — CRM Deal Note Added": NOTE_DEAL_PIPELINE,
	"CRM Slack — CRM Deal Inactivity (7 days)": DEAL_PIPELINE,
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
	would hide variants.
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
		new = frappe.db.get_value("CRM Pipeline", new, "name") or (
			frappe.get_doc({"doctype": "CRM Pipeline", "pipeline_name": new})
			.insert(ignore_permissions=True)
			.name
		)
		# direct update: touching `modified` would fire "Deal updated" for every deal
		frappe.qb.update(deal).set(deal.custom_pipeline, new).where(trimmed == old).run()


def split_notifications():
	webhook = CSM_WEBHOOK if frappe.db.exists("Slack Webhook URL", CSM_WEBHOOK) else None
	for name, pipeline in ALERTS.items():
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
		# the alert's own condition, without the routing check (also when re-running);
		# the old renewal rule (or no condition) is replaced, any other condition is kept in both alerts
		if old == not_csm:
			own = ""
		elif old.endswith(f" and {not_csm}"):
			own = old.removesuffix(f" and {not_csm}")
		elif CSM_KEYWORD in old:
			# a differently spelled renewal rule would make the CSM copy never fire
			frappe.throw(f"Fix the {CSM_KEYWORD!r} condition on {name!r} by hand, then re-run migrate: {old}")
		else:
			own = f"({old})" if old else ""
		base = f"{own} and " if own else ""
		csm_name = name + SUFFIX
		if not frappe.db.exists("Notification", csm_name):
			csm = frappe.copy_doc(sales)
			csm.name = csm_name
			csm.condition = base + is_csm
			csm.slack_webhook_url = webhook
			csm.enabled = 0
			csm.insert(ignore_permissions=True)
		sales.condition = base + not_csm
		sales.save(ignore_permissions=True)

	inactivity = "CRM Slack — CRM Deal Inactivity (7 days)" + SUFFIX
	if frappe.db.exists("Notification", inactivity) and not frappe.db.get_single_value(
		"CRM XT Settings", "deal_inactivity_csm_notification"
	):  # don't undo an admin clearing it
		frappe.db.set_single_value("CRM XT Settings", "deal_inactivity_csm_notification", inactivity)
