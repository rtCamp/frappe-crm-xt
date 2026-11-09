import frappe
from frappe.query_builder import functions as fn
from frappe.utils import now

from frappe_crm_xt.doc_events.deal import ORGANIZATION_FIELDS, is_deal_link


def sync_deals(org, method=None):
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
	deal = frappe.qb.DocType("CRM Deal")
	for field, previous in changed.items():
		blank = 0 if field == "annual_revenue" else ""
		# one conditional update, so a deal edited meanwhile is checked as it is now
		(
			frappe.qb.update(deal)
			.set(deal[field], new[field])
			.set(deal.modified, now())
			.where(deal.organization == org.name)
			.where(fn.IfNull(deal[field], blank).isin([blank, previous or blank]))
		).run()


def on_address_validate(doc, method=None):
	"""Deal links follow the address's organizations: a newly linked organization brings its deals,
	an unlinked one takes them away; a deal link removed by hand stays removed."""
	before = doc.get_doc_before_save()
	old, new = organizations(before), organizations(doc)
	if unlinked := list(old - new):
		removed = set(frappe.get_all("CRM Deal", {"organization": ("in", unlinked)}, pluck="name"))
		doc.set("links", [row for row in doc.links if not is_deal_link(row, removed)])
	link_organization_deals(doc, list(new - old))


def organizations(address):
	links = address.links if address else []
	return {link.link_name for link in links if link.link_doctype == "CRM Organization"}


def link_organization_deals(address, orgs):
	"""Each deal of these organizations is linked to the address, so it shows on the deal."""
	if not orgs:
		return
	linked = {link.link_name for link in address.links if link.link_doctype == "CRM Deal"}
	for deal in frappe.get_all("CRM Deal", {"organization": ("in", orgs)}, pluck="name"):
		if deal not in linked:
			address.append("links", {"link_doctype": "CRM Deal", "link_name": deal})
