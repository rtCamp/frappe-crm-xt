import frappe

from frappe_crm_xt.doc_events.deal import ORGANIZATION_FIELDS


def sync_deals(org, method=None):
	"""A changed organization detail is copied as saved to its deals the user may access,
	replacing their value."""
	before = org.get_doc_before_save()
	if not before:
		return
	# stored form: an unset revenue is 0, as in the NOT NULL column
	new, old = org.get_valid_dict(), before.get_valid_dict()
	if not (changed := {f: new[f] for f in ORGANIZATION_FIELDS if old[f] != new[f]}):
		return
	# get_list, not get_all: only the deals this user may access (FCRM's deal permission rules)
	deals = frappe.get_list("CRM Deal", {"organization": org.name}, pluck="name", limit_page_length=0)
	if not deals:
		return
	# the deals keep their modified time: the organization changed, not the deal
	frappe.db.set_value("CRM Deal", {"name": ("in", deals)}, changed, update_modified=False)
	for name in deals:
		# an open CRM deal page refetches on list_update, so it shows the new values
		frappe.publish_realtime("list_update", {"doctype": "CRM Deal", "name": name}, after_commit=True)
