# Copyright (c) 2026, rtCamp and contributors
# For license information, please see license.txt

import frappe
from crm.api.command_palette import SEARCH_TYPES
from frappe.tests import IntegrationTestCase

from frappe_crm_xt.api.command_palette import search


class TestCommandPaletteSearch(IntegrationTestCase):
	def test_deal_matches_and_shows_by_title(self):
		"""A deal is found by its Title and shows it as the result title"""
		title = f"XT-Title-{frappe.generate_hash(length=8)}"
		deal = frappe.get_doc({"doctype": "CRM Deal", "title": title}).insert(ignore_permissions=True)

		matches = {(m["doctype"], m["name"]): m["title"] for m in search(query=title)["matches"]}

		self.assertEqual(matches.get(("CRM Deal", deal.name)), title)
		recent = search(recent_names=frappe.as_json({"CRM Deal": [deal.name]}))["recent"]
		self.assertEqual([r["title"] for r in recent], [title])
		# CRM's module is shared across sites, so the override must leave it alone.
		self.assertEqual(SEARCH_TYPES["CRM Deal"][1], "organization")
