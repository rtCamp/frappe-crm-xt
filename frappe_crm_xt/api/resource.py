from __future__ import annotations

import frappe
from frappe import _

ALLOWED_DOCTYPES = frozenset({"CRM Lead", "CRM Deal"})


@frappe.whitelist(methods=["GET"])
def get_data(
	doctype: str,
	fields: str | list | None = None,
	filters: str | dict | list | None = None,
	or_filters: str | dict | list | None = None,
	order_by: str | None = None,
	start: int = 0,
	limit: int = 20,
):
	if doctype not in ALLOWED_DOCTYPES:
		frappe.throw(_("Doctype {0} is not allowed").format(doctype), frappe.PermissionError)

	frappe.only_for("Marketing bot")

	return frappe.get_all(
		doctype,
		fields=frappe.parse_json(fields) if fields else ["name"],
		filters=frappe.parse_json(filters) if filters else None,
		or_filters=frappe.parse_json(or_filters) if or_filters else None,
		order_by=order_by,
		start=start,
		limit=limit,
	)
