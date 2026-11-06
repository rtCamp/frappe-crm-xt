import frappe

from frappe_crm_xt.doc_events.deal import ORGANIZATION_FIELDS

ORGANIZATION = "CRM Organization"


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
	# not currency: the deal's amounts and product rates are in its own currency and are not converted
	changed = {f: old[f] for f in ORGANIZATION_FIELDS if f != "currency" and old[f] != new[f]}
	if not changed:
		return
	for deal in frappe.get_all("CRM Deal", {"organization": org.name}, ["name", *changed]):
		values = {f: new[f] for f, previous in changed.items() if not deal[f] or deal[f] == previous}
		if values:
			frappe.db.set_value("CRM Deal", deal.name, values)


def on_address_update(doc, method=None):
	"""An organization newly linked to the address brings its deals; a deal link removed by hand
	stays removed, as the organization's links did not change."""
	before = doc.get_doc_before_save()
	known = (
		{link.link_name for link in before.links if link.link_doctype == ORGANIZATION} if before else set()
	)
	current = [link.link_name for link in doc.links if link.link_doctype == ORGANIZATION]
	link_organization_deals(doc, [org for org in current if org not in known])


def link_organization_deals(address, orgs):
	"""Each deal of these organizations is linked to the address, so it shows on the deal."""
	if not orgs:
		return
	linked = {link.link_name for link in address.links if link.link_doctype == "CRM Deal"}
	for deal in frappe.get_all("CRM Deal", {"organization": ("in", orgs)}, pluck="name"):
		if deal not in linked:
			# rows only, no Address save: its validations (e.g. GSTIN) must not block a deal save
			address.append("links", {"link_doctype": "CRM Deal", "link_name": deal}).db_insert()


def relink_deal_addresses(deal):
	"""Deal on_update with a new organization: its former organization's addresses go, its new
	organization's come; an address added to the deal by hand stays."""
	before = deal.get_doc_before_save()
	new = organization_addresses(deal.organization)
	if stale := [name for name in organization_addresses(before and before.organization) if name not in new]:
		frappe.db.delete("Dynamic Link", {**deal_link(deal.name), "parent": ("in", stale)})
	for name in new:
		if not frappe.db.exists("Dynamic Link", {**deal_link(deal.name), "parent": name}):
			frappe.get_doc("Address", name).append("links", deal_link(deal.name)).db_insert()


def organization_addresses(organization):
	if not organization:
		return []
	return frappe.get_all(
		"Dynamic Link",
		{"parenttype": "Address", "link_doctype": ORGANIZATION, "link_name": organization},
		pluck="parent",
	)


def deal_link(deal):
	return {"parenttype": "Address", "link_doctype": "CRM Deal", "link_name": deal}
