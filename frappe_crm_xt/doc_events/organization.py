import frappe

from frappe_crm_xt.doc_events.deal import ORGANIZATION_FIELDS


def sync_deals(org, method=None):
	"""Copy changed organization details to all its deals."""
	before = org.get_doc_before_save()
	if not before:
		return
	# stored form: an unset revenue is 0, as in the NOT NULL column
	new, old = org.get_valid_dict(), before.get_valid_dict()
	if not (changed := {f: new[f] for f in ORGANIZATION_FIELDS if old[f] != new[f]}):
		return
	# organization data, not deal data: a user who may edit the organization updates all its deals
	deals = frappe.get_all("CRM Deal", {"organization": org.name}, pluck="name")
	# filtered on the organization, so a deal moved to another one meanwhile is left alone;
	# the deals keep their modified time: the organization changed, not the deal
	frappe.db.set_value("CRM Deal", {"organization": org.name}, changed, update_modified=False)
	for name in deals:
		# an open CRM deal page refetches on list_update, so it shows the new values
		frappe.publish_realtime(
			"list_update", {"doctype": "CRM Deal", "name": name}, doctype="CRM Deal", after_commit=True
		)
