"""Fill existing deals' blank organization details and link the organization's addresses to them.

Idempotent: only blanks are filled and only missing address links added.
"""

import frappe
from frappe.query_builder import functions as fn
from pypika.terms import Bracket

from frappe_crm_xt.doc_events.deal import ORGANIZATION_FIELDS
from frappe_crm_xt.doc_events.organization import link_organization_deals


def execute():
	deal = frappe.qb.DocType("CRM Deal")
	organization = frappe.qb.DocType("CRM Organization")

	def value(field):
		# a subquery, not a join: pypika leaves SET columns unqualified, ambiguous across both tables;
		# bracketed, as pypika does not wrap a subquery in SET
		return Bracket(
			frappe.qb.from_(organization)
			.select(organization[field])
			.where(organization.name == deal.organization)
		)

	for field in ORGANIZATION_FIELDS:
		blank = 0 if field == "annual_revenue" else ""
		filled = frappe.qb.from_(organization).where(fn.IfNull(organization[field], blank) != blank)
		(
			frappe.qb.update(deal)
			.set(deal[field], value(field))
			.where(fn.IfNull(deal[field], blank) == blank)
			.where(deal.organization.isin(filled.select(organization.name)))
		).run()

	for name in frappe.get_all(
		"Dynamic Link",
		{"parenttype": "Address", "link_doctype": "CRM Organization"},
		pluck="parent",
		distinct=True,
	):
		address = frappe.get_doc("Address", name)
		orgs = [link.link_name for link in address.links if link.link_doctype == "CRM Organization"]
		link_organization_deals(address, orgs)
