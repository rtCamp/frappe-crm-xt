import json
from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
	"""Apply customisations and seed default field layouts (install only)."""
	install()
	install_fields_layout()


def install():
	"""Apply all rtcamp-side CRM customisations (idempotent; runs on migrate)."""
	install_custom_fields()
	install_property_setters()


def install_custom_fields():
	"""Install / refresh custom fields from custom_fields.json."""
	data_file = Path(__file__).parent / "custom_fields.json"
	custom_fields = json.loads(data_file.read_text())
	# Owner tag so /desk/custom-field shows who created these fields.
	for fields in custom_fields.values():
		for df in fields:
			df.setdefault("module", "Frappe Crm Xt")
	create_custom_fields(custom_fields, update=True)


def install_property_setters():
	"""Install / refresh property setters from property_setters.json."""
	data_file = Path(__file__).parent / "property_setters.json"
	for ps in json.loads(data_file.read_text()):
		frappe.make_property_setter(
			{
				"doctype": ps["doctype"],
				"doctype_or_field": "DocType" if ps.get("for_doctype") else "DocField",
				"fieldname": ps.get("fieldname"),
				"property": ps["property"],
				"value": ps["value"],
				"property_type": ps["property_type"],
			},
			validate_fields_for_doctype=False,
			module="Frappe Crm Xt",
		)


def install_fields_layout():
	"""Seed/refresh default CRM field layouts, overwriting existing ones (install only)."""
	data_file = Path(__file__).parent / "crm_fields_layout.json"
	for entry in json.loads(data_file.read_text()):
		if frappe.db.exists("CRM Fields Layout", entry["name"]):
			doc = frappe.get_doc("CRM Fields Layout", entry["name"])
			doc.layout = entry["layout"]
			doc.save(ignore_permissions=True)
		else:
			frappe.get_doc(
				{
					"doctype": "CRM Fields Layout",
					"dt": entry["dt"],
					"type": entry["type"],
					"layout": entry["layout"],
				}
			).insert(ignore_permissions=True)
