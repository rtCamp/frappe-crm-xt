"""Set Customer.custom_crm_organization from deals that already know the pairing.

Customers FCRM creates on Won never had it set, which the Deal Project filter relies on.
Idempotent: only fills blanks, never overwrites an existing link.

Edge cases:
- Customer on several deals of the same organization → linked once.
- Customer on deals of different organizations → ambiguous, skipped (link by hand).
- Deal without organization, or pointing at a deleted Customer/Organization → ignored.
"""

import frappe
from frappe.query_builder import functions as fn


def execute():
	if not (
		frappe.db.has_column("Customer", "custom_crm_organization")
		and frappe.db.has_column("CRM Deal", "erpnext_customer")
	):
		return

	deal = frappe.qb.DocType("CRM Deal")
	customer = frappe.qb.DocType("Customer")
	organization = frappe.qb.DocType("CRM Organization")

	pairs = (
		frappe.qb.from_(deal)
		.join(customer)
		.on(customer.name == deal.erpnext_customer)
		.join(organization)
		.on(organization.name == deal.organization)
		.select(customer.name, fn.Max(deal.organization))
		.where(fn.IfNull(customer.custom_crm_organization, "") == "")
		.groupby(customer.name)
		.having(fn.Count(deal.organization).distinct() == 1)
	).run()

	for customer_name, organization_name in pairs:
		frappe.db.set_value(
			"Customer", customer_name, "custom_crm_organization", organization_name, update_modified=False
		)
