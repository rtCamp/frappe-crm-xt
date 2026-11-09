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

	def test_changes_reach_all_deals(self):
		"""A changed organization detail replaces the value on every deal, its own one too"""
		synced, own = self.deal(), self.deal(website="https://own.example")
		self.org.website = "https://new.example"
		self.org.save(ignore_permissions=True)
		for deal in (synced, own):
			self.assertEqual(frappe.db.get_value("CRM Deal", deal.name, "website"), "https://new.example")

	def test_revenue_follows_organization(self):
		"""Every deal takes the organization's new revenue, a value set on the deal too"""
		blank, old, own = self.deal(), self.deal(), self.deal()
		self.org.annual_revenue = 100
		self.org.save(ignore_permissions=True)
		frappe.db.set_value("CRM Deal", own.name, "annual_revenue", 7)
		self.org.annual_revenue = 200
		self.org.save(ignore_permissions=True)
		revenue = lambda d: frappe.db.get_value("CRM Deal", d.name, "annual_revenue")  # noqa: E731
		self.assertEqual((revenue(blank), revenue(old), revenue(own)), (200, 200, 200))

	def test_patch_fills_only_blank_deal_fields(self):
		"""The backfill fills blank deal fields, keeps a deal's own value, and can rerun"""
		from frappe_crm_xt.patches.v1_0.fill_deals_from_organization import execute

		self.org.update({"no_of_employees": "51-200", "annual_revenue": 300, "custom_key_account": 1})
		self.org.save(ignore_permissions=True)
		blank, own = self.deal(), self.deal()
		# deals made before the fill existed: blank details
		blanked = {"website": None, "no_of_employees": None, "annual_revenue": 0, "custom_key_account": 0}
		frappe.db.set_value("CRM Deal", blank.name, blanked)
		frappe.db.set_value("CRM Deal", own.name, {**blanked, "no_of_employees": "1-10"})
		fields = ["website", "no_of_employees", "annual_revenue", "custom_key_account"]
		for _ in range(2):
			execute()
			self.assertEqual(
				frappe.db.get_value("CRM Deal", blank.name, fields), ("https://old.example", "51-200", 300, 1)
			)
			self.assertEqual(frappe.db.get_value("CRM Deal", own.name, "no_of_employees"), "1-10")

	def test_open_deal_pages_are_told_to_reload(self):
		"""Each synced deal gets a doc_update event, so an open deal page reloads"""
		from unittest.mock import patch

		deals = {self.deal().name, self.deal().name}
		self.org.website = "https://new.example"
		with patch("frappe.publish_realtime") as publish:
			self.org.save(ignore_permissions=True)
		updated = {c.kwargs["docname"] for c in publish.call_args_list if c.args[0] == "doc_update"}
		self.assertLessEqual(deals, updated)

	def test_sales_user_updates_only_their_deals(self):
		"""A Sales User's organization change reaches only the deals they may access"""
		user = "xt-sync-sales-user@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{"doctype": "User", "email": user, "first_name": "XT Sync", "send_welcome_email": 0}
			).insert(ignore_permissions=True).add_roles("Sales User")
		mine, other = self.deal(deal_owner=user), self.deal(deal_owner="Administrator")
		frappe.set_user(user)
		try:
			org = frappe.get_doc("CRM Organization", self.org.name)
			org.website = "https://new.example"
			org.save()
		finally:
			frappe.set_user("Administrator")
		website = lambda d: frappe.db.get_value("CRM Deal", d.name, "website")  # noqa: E731
		self.assertEqual((website(mine), website(other)), ("https://new.example", "https://old.example"))
