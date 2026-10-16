import json

import frappe

LAYOUT = "CRM Deal-Data Fields"
ANCHOR = "custom_current_host"
FIELDNAME = "tech_stack"


def execute():
	if not frappe.db.exists("CRM Fields Layout", LAYOUT):
		return

	doc = frappe.get_doc("CRM Fields Layout", LAYOUT)
	tabs = json.loads(doc.layout or "[]")
	columns = [
		column for tab in tabs for section in tab.get("sections", []) for column in section.get("columns", [])
	]
	if any(FIELDNAME in column.get("fields", []) for column in columns):
		return

	for column in columns:
		fields = column.get("fields", [])
		if ANCHOR in fields:
			fields.insert(fields.index(ANCHOR) + 1, FIELDNAME)
			doc.layout = json.dumps(tabs)
			doc.save(ignore_permissions=True)
			return
