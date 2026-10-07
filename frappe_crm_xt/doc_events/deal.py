from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, get_link_to_form

from frappe_crm_xt.frappe_crm_xt.doctype.crm_stage_change_log.crm_stage_change_log import (
	add_stage_change_log,
)
from frappe_crm_xt.utils.gmail_thread import link_gmail_threads


def validate(doc, method=None):
	validate_probability(doc)


def validate_probability(doc):
	probability = flt(doc.get("probability"), 2)
	if probability < 0 or probability > 100:
		frappe.throw(
			_("Probability must be between 0 and 100 (got {0}).").format(probability),
			frappe.ValidationError,
		)


def before_save(doc, method=None):
	current_status = frappe.db.get_value("CRM Deal", doc.name, "status")
	current_stage = frappe.db.get_value("CRM Deal", doc.name, "sales_stage")
	if not current_status and not current_stage:
		# Brand-new record — after_insert handles it
		return

	if doc.status != current_status:
		create_checklist(doc, field="status", value=doc.status)
	if doc.sales_stage != current_stage:
		create_checklist(doc, field="sales_stage", value=doc.sales_stage)
		add_stage_change_log(doc)


def after_insert(doc, method=None):
	create_checklist(doc, field="status", value=doc.status)
	create_checklist(doc, field="sales_stage", value=doc.sales_stage)
	move_lead_emails(doc)


def move_lead_emails(doc):
	"""Carry the source lead's email threads over to the deal it converted into."""
	if not doc.get("lead"):
		return
	if "frappe_gmail_thread" not in frappe.get_installed_apps():
		return
	link_gmail_threads("CRM Lead", doc.lead, doc)


# ─── internal ────────────────────────────────────────────────────────────────

# field → checklist parenttype on tabCRM Deal Status Checklist
_PARENTTYPE_FOR = {
	"status": "CRM Deal Status",
	"sales_stage": "Sales Stage",
}


def create_checklist(doc, field=None, value=None):
	if not field or not value:
		return

	parenttype = _PARENTTYPE_FOR.get(field)
	if not parenttype:
		return

	checklist_items = frappe.get_all(
		"CRM Deal Status Checklist",
		filters={"parent": value, "parenttype": parenttype},
		fields=["checklist_item"],
		pluck="checklist_item",
		ignore_permissions=True,
	)
	if not checklist_items:
		return

	title = _("Checklist for {0}").format(value)

	# Idempotency: don't recreate when an active task with the same title
	# already exists on this deal.
	existing = frappe.get_all(
		"CRM Task",
		filters={
			"reference_doctype": "CRM Deal",
			"reference_docname": doc.name,
			"title": title,
			"status": ["not in", ["Done", "Canceled"]],
		},
		limit=1,
		ignore_permissions=True,
	)
	if existing:
		return

	# Build a TipTap task-list (the format CRM's editor uses for checklists).
	# Each task item must include the empty <label><input><span></label> markup
	# so the rendered editor shows the checkbox, and wrap the text in <div><p>.
	items_html = "".join(
		(
			'<li data-checked="false" data-type="taskItem">'
			'<label><input type="checkbox"><span></span></label>'
			f"<div><p>{frappe.utils.escape_html(item)}</p></div>"
			"</li>"
		)
		for item in checklist_items
	)
	description = f'<ul data-type="taskList">{items_html}</ul>'

	frappe.get_doc(
		{
			"doctype": "CRM Task",
			"title": title,
			"description": description,
			"reference_doctype": "CRM Deal",
			"reference_docname": doc.name,
			"assigned_to": doc.deal_owner or frappe.session.user,
			"status": "Todo",
		}
	).insert(ignore_permissions=True)


DEAL_TO_PROJECT_FIELD_MAP: dict[str, str] = {
	"erpnext_customer": "customer",
	"company": "company",
	"industry": "custom_industry",
	"territory": "custom_territory",
	"currency": "custom_currency",
	"custom_estimatedpurchased_hours": "custom_total_hours_purchased",
	"custom_project_manager": "custom_project_manager",
	"contact": "custom_client_point_of_contact",
	"custom_service_type": "custom_service_type",
	"custom_project_type": "project_type",
	"custom__project_size": "custom_project_size",
	"custom_complexity_level": "custom_complexity",
	"custom_duration": "custom_duration",
	"custom_billing_type": "custom_billing_type",
	"custom_timezone": "custom_timezone",
	"custom_previous_cms": "custom_previous_cms",
	"custom_current_host": "custom_host",
	"custom_deal_type": "custom_deal_type",
	"custom_restricted_under_nda": "custom_restricted_under_nda",
	"custom_description": "notes",
	"custom_expected_start_date": "expected_start_date",
}

REQUIRED_DEAL_FIELDS_FOR_PROJECT: tuple[str, ...] = (
	"erpnext_customer",
	"company",
	"industry",
	"territory",
	"currency",
	"custom_estimatedpurchased_hours",
	"custom_project_manager",
	"custom_service_type",
	"custom_project_type",
	"custom__project_size",
	"custom_complexity_level",
	"custom_duration",
	"custom_billing_type",
	"custom_timezone",
	"custom_previous_cms",
	"custom_current_host",
	"custom_deal_type",
	"custom_description",
)


# Can be used if required
def _auto_create_project_on_won(doc):
	if doc.status != "Won":
		return
	if frappe.db.exists("Project", {"custom_deal": doc.name}):
		return
	if any(not doc.get(f) for f in REQUIRED_DEAL_FIELDS_FOR_PROJECT):
		return
	_create_project(doc)


def _create_project(deal) -> str:
	values = {"doctype": "Project", "status": "Open", "custom_deal": deal.name}
	for deal_field, project_field in DEAL_TO_PROJECT_FIELD_MAP.items():
		if deal_field == "custom_service_type":
			values[project_field] = [{"service_type": row.service_type} for row in deal.get(deal_field) or []]
			continue
		values[project_field] = deal.get(deal_field)

	base_name = deal.get("organization_name") or deal.name
	values["project_name"] = f"{base_name} - {deal.name}"
	values["estimated_costing"] = deal.get("expected_deal_value") or deal.get("deal_value") or 0

	project = frappe.get_doc(values).insert(ignore_permissions=True)
	frappe.msgprint(
		_("Project {0} created.").format(get_link_to_form("Project", project.name)),
		alert=True,
		indicator="green",
	)
	return project.name
