"""Migrate custom_service_type from a single-value field to Table MultiSelect.

Service Type moves from a single Link field on CRM Deal and Project to a
Table MultiSelect (`CRM Service Type` child rows), so a record can carry more
than one Service Type. CRM Lead's free-text custom_service_type field is out
of scope and is left untouched. This patch runs in [post_model_sync] — after
the new `CRM Service Type` child table has been created by sync_all(), but
before the `frappe_crm_xt.setup.install` after_migrate hook rewrites the
custom field definitions and drops the old columns — so it's the last point
the old single value can still be read.

Custom Field disallows a Link/Data field turning into a Table MultiSelect in
place (see CustomizeForm.ALLOWED_FIELDTYPE_CHANGE) -- deleting the old field
here (metadata only, the physical column is untouched) makes the
after_migrate hook insert it fresh as Table MultiSelect instead of failing
trying to update it.
"""

import frappe
from frappe.model.document import bulk_insert

CHILD_DOCTYPE = "CRM Service Type"
CHILD_FIELDNAME = "custom_service_type"

OLD_CUSTOM_FIELDS = (
	"CRM Deal-custom_service_type",
	"Project-custom_service_type",
)


def execute():
	docs = []
	docs += _link_field_docs("CRM Deal")
	docs += _link_field_docs("Project")

	if docs:
		bulk_insert(CHILD_DOCTYPE, docs, ignore_duplicates=True)

	for name in OLD_CUSTOM_FIELDS:
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, ignore_permissions=True)


def _link_field_docs(parent_doctype: str) -> list:
	"""CRM Deal / Project: custom_service_type was a Link column."""
	if not frappe.db.has_column(parent_doctype, "custom_service_type"):
		return []

	rows = frappe.get_all(
		parent_doctype,
		filters=[["custom_service_type", "!=", ""]],
		fields=["name", "custom_service_type"],
	)
	return [_child_doc(parent_doctype, row.name, row.custom_service_type) for row in rows]


def _child_doc(parent_doctype: str, parent_name: str, service_type: str):
	doc = frappe.get_doc(
		{
			"doctype": CHILD_DOCTYPE,
			"service_type": service_type,
			"parent": parent_name,
			"parenttype": parent_doctype,
			"parentfield": CHILD_FIELDNAME,
			"idx": 1,
		}
	)
	doc.set_new_name()
	return doc
