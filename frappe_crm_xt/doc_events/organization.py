import frappe
from frappe.query_builder import functions as fn
from frappe.utils import now

from frappe_crm_xt.doc_events.deal import ORGANIZATION_FIELDS


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
