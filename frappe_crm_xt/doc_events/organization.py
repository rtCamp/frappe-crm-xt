import frappe

from frappe_crm_xt.doc_events.deal import ORGANIZATION_FIELDS


def sync_deals(org, method=None):
	"""A changed organization detail is copied as saved to all its deals, replacing their value."""
	before = org.get_doc_before_save()
	if not before:
		return
	# stored form: an unset revenue is 0, as in the NOT NULL column
	new, old = org.get_valid_dict(), before.get_valid_dict()
	if changed := {f: new[f] for f in ORGANIZATION_FIELDS if old[f] != new[f]}:
		frappe.db.set_value("CRM Deal", {"organization": org.name}, changed)
