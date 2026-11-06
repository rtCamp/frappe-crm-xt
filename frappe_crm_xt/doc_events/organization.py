import frappe

from frappe_crm_xt.doc_events.deal import ORGANIZATION_FIELDS


def on_update(doc, method=None):
	sync_deals(doc)


def sync_deals(org):
	"""A changed organization detail goes to its deals that were blank or still held the old value;
	a value set on the deal itself is kept."""
	before = org.get_doc_before_save()
	if not before:
		return
	# stored form: an unset revenue is 0, as in the NOT NULL column
	new, old = org.get_valid_dict(), before.get_valid_dict()
	changed = {f: old[f] for f in ORGANIZATION_FIELDS if old[f] != new[f]}
	if not changed:
		return
	for deal in frappe.get_all("CRM Deal", {"organization": org.name}, ["name", *changed]):
		values = {f: new[f] for f, previous in changed.items() if not deal[f] or deal[f] == previous}
		if "currency" in values:
			values["exchange_rate"] = org.exchange_rate
		if values:
			frappe.db.set_value("CRM Deal", deal.name, values)


def on_address_update(doc, method=None):
	link_organization_deals(doc)


def link_organization_deals(address):
	"""An organization's address is linked to each of its deals, so it shows on the deal."""
	orgs = [link.link_name for link in address.links if link.link_doctype == "CRM Organization"]
	if not orgs:
		return
	linked = {link.link_name for link in address.links if link.link_doctype == "CRM Deal"}
	for deal in frappe.get_all("CRM Deal", {"organization": ("in", orgs)}, pluck="name"):
		if deal not in linked:
			# rows only, no Address save: its validations (e.g. GSTIN) must not block a deal save
			address.append("links", {"link_doctype": "CRM Deal", "link_name": deal}).db_insert()


def link_addresses_to_deal(deal):
	for name in frappe.get_all(
		"Dynamic Link",
		{"parenttype": "Address", "link_doctype": "CRM Organization", "link_name": deal.organization},
		pluck="parent",
	):
		link_organization_deals(frappe.get_doc("Address", name))
