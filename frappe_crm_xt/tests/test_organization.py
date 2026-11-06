# Copyright (c) 2026, rtCamp and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase


class TestOrganizationEvents(IntegrationTestCase):
	def setUp(self):
		self.org = frappe.get_doc(
			{
				"doctype": "CRM Organization",
				"organization_name": f"XT-Org-{frappe.generate_hash(length=8)}",
				"website": "https://old.example",
			}
		).insert(ignore_permissions=True)

	def deal(self, **values):
		return frappe.get_doc({"doctype": "CRM Deal", "organization": self.org.name, **values}).insert(
			ignore_permissions=True
		)

	def test_changes_reach_deals_without_their_own_value(self):
		"""Blank or old values follow the organization; a deal's own value is kept"""
		synced, own = self.deal(), self.deal(website="https://own.example")
		self.org.website = "https://new.example"
		self.org.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("CRM Deal", synced.name, "website"), "https://new.example")
		self.assertEqual(frappe.db.get_value("CRM Deal", own.name, "website"), "https://own.example")

	def test_organization_addresses_are_linked_to_deals(self):
		"""Addresses added before and after a deal are linked to it"""

		before = self.address(self.org.name)
		deal = self.deal()
		after = self.address(self.org.name)
		for name in (before.name, after.name):
			self.assertTrue(self.deal_linked(name, deal.name))

	def address(self, org, doctype="CRM Organization"):
		return frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": f"XT {frappe.generate_hash(length=6)}",
				"address_line1": "1 Street",
				"city": "Austin",
				"country": "United States",
				"links": [{"link_doctype": doctype, "link_name": org}],
			}
		).insert(ignore_permissions=True)

	def deal_linked(self, address, deal):
		return bool(
			frappe.db.exists(
				"Dynamic Link", {"parent": address, "link_doctype": "CRM Deal", "link_name": deal}
			)
		)

	def test_new_organization_swaps_addresses(self):
		"""A deal moved to another organization loses the old organization's addresses, keeps its own"""
		other = frappe.get_doc(
			{"doctype": "CRM Organization", "organization_name": f"XT-Org-{frappe.generate_hash(length=8)}"}
		).insert(ignore_permissions=True)
		old, new = self.address(self.org.name), self.address(other.name)
		deal = self.deal()
		own = self.address(deal.name, "CRM Deal")
		deal.reload()
		deal.organization = other.name
		deal.save(ignore_permissions=True)
		self.assertFalse(self.deal_linked(old.name, deal.name))
		self.assertTrue(self.deal_linked(new.name, deal.name))
		self.assertTrue(self.deal_linked(own.name, deal.name))

	def test_unlinked_deal_stays_unlinked(self):
		"""Removing a deal from an organization's address is not undone by the address save"""
		deal = self.deal()
		address = self.address(self.org.name)
		address.links = [link for link in address.links if link.link_doctype != "CRM Deal"]
		address.save(ignore_permissions=True)
		self.assertFalse(self.deal_linked(address.name, deal.name))
