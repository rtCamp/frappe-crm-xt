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

		def address(title):
			return frappe.get_doc(
				{
					"doctype": "Address",
					"address_title": title,
					"address_line1": "1 Street",
					"city": "Austin",
					"country": "United States",
					"links": [{"link_doctype": "CRM Organization", "link_name": self.org.name}],
				}
			).insert(ignore_permissions=True)

		before = address("XT Before")
		deal = self.deal()
		after = address("XT After")
		for name in (before.name, after.name):
			self.assertTrue(
				frappe.db.exists(
					"Dynamic Link",
					{"parent": name, "link_doctype": "CRM Deal", "link_name": deal.name},
				)
			)
