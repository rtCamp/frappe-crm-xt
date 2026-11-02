"""Move CRM Deal.custom_sow_sheet_link → custom_handover_sheet_link."""

import click
import frappe

from frappe_crm_xt.setup import install_custom_fields

OLD_FIELD = "custom_sow_sheet_link"
NEW_FIELD = "custom_handover_sheet_link"


def execute():
	old_cf = f"CRM Deal-{OLD_FIELD}"
	if not frappe.db.exists("Custom Field", old_cf):
		return

	install_custom_fields()

	if frappe.db.has_column("CRM Deal", OLD_FIELD):
		deal = frappe.qb.DocType("CRM Deal")
		old, new = deal[OLD_FIELD], deal[NEW_FIELD]
		frappe.qb.update(deal).set(new, old).where(
			(old.isnotnull()) & (old != "") & (new.isnull() | (new == ""))
		).run()

	_update_saved_layouts()

	frappe.delete_doc("Custom Field", old_cf, force=True)
	frappe.db.commit()

	click.secho(f"  CRM Deal.{OLD_FIELD} → {NEW_FIELD}", fg="green")


def _update_saved_layouts():
	"""Point saved CRM Fields Layouts at the new fieldname."""
	if not frappe.db.exists("DocType", "CRM Fields Layout"):
		return

	old_ref, new_ref = f'"{OLD_FIELD}"', f'"{NEW_FIELD}"'
	for name, layout in frappe.get_all("CRM Fields Layout", fields=["name", "layout"], as_list=True):
		if layout and old_ref in layout and new_ref not in layout:
			frappe.db.set_value(
				"CRM Fields Layout",
				name,
				"layout",
				layout.replace(old_ref, new_ref),
				update_modified=False,
			)
