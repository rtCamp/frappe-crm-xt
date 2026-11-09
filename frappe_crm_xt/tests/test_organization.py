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

	def test_revenue_follows_organization(self):
		"""A deal with no revenue, or the old one, takes the organization's new revenue"""
		blank, old, own = self.deal(), self.deal(), self.deal()
		self.org.annual_revenue = 100
		self.org.save(ignore_permissions=True)
		frappe.db.set_value("CRM Deal", own.name, "annual_revenue", 7)
		self.org.annual_revenue = 200
		self.org.save(ignore_permissions=True)
		revenue = lambda d: frappe.db.get_value("CRM Deal", d.name, "annual_revenue")  # noqa: E731
		self.assertEqual((revenue(blank), revenue(old), revenue(own)), (200, 200, 7))

	def test_patch_fills_only_blank_deal_fields(self):
		"""The backfill fills blank deal fields, keeps a deal's own value, and can rerun"""
		from frappe_crm_xt.patches.v1_0.fill_deals_from_organization import execute

		self.org.update({"no_of_employees": "51-200", "annual_revenue": 300})
		self.org.save(ignore_permissions=True)
		blank, own = self.deal(), self.deal()
		# deals made before the fill existed: blank details
		blanked = {"website": None, "no_of_employees": None, "annual_revenue": 0}
		frappe.db.set_value("CRM Deal", blank.name, blanked)
		frappe.db.set_value("CRM Deal", own.name, {**blanked, "no_of_employees": "1-10"})
		fields = ["website", "no_of_employees", "annual_revenue"]
		for _ in range(2):
			execute()
			self.assertEqual(
				frappe.db.get_value("CRM Deal", blank.name, fields), ("https://old.example", "51-200", 300)
			)
			self.assertEqual(frappe.db.get_value("CRM Deal", own.name, "no_of_employees"), "1-10")
