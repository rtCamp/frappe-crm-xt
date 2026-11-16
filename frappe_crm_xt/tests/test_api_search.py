# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from frappe.tests import UnitTestCase

from frappe_crm_xt.api.search import (
	LINK_PAGE_LENGTH,
	search_link,
)


class TestApiSearch(UnitTestCase):
	def test_search_link_defaults_to_link_page_length(self):
		"""search_link with page_length=None returns at most LINK_PAGE_LENGTH rows"""
		rows = search_link(doctype="User", txt="", page_length=None)

		self.assertLessEqual(len(rows), LINK_PAGE_LENGTH)

	def test_search_link_runs_with_explicit_page_length(self):
		"""search_link honours an explicit page_length"""
		search_link(doctype="User", txt="", page_length=5)
