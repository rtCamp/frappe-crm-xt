# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import UnitTestCase

from frappe_crm_xt.api.search import (
	LINK_PAGE_LENGTH,
	_clean_excerpt,
	get_search_results,
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

	def test_get_search_results_shape(self):
		"""get_search_results returns a 2-tuple (results, has_more)"""
		result = get_search_results(text="", start=0, limit=5)

		self.assertEqual(len(result), 2)
		results, has_more = result
		# results is an iterable of dicts (or empty)
		for row in results:
			self.assertIsInstance(row, dict)
		self.assertIsInstance(has_more, bool)

	def test_get_search_results_coerces_string_ints(self):
		"""get_search_results coerces start/limit when passed as strings"""
		results, has_more = get_search_results(text="", start="0", limit="3")

		self.assertIsInstance(has_more, bool)
		for row in results:
			self.assertIsInstance(row, dict)

	def test_get_search_results_rejects_unknown_filter(self):
		"""An unrecognised filter key in `doctypes` raises, not silently ignored"""
		with self.assertRaises(frappe.ValidationError):
			get_search_results(text="x", doctypes=["Not A Real Filter"])


class TestCleanExcerpt(UnitTestCase):
	def test_strips_leading_name_field(self):
		"""The leading "Name: <docname>" field is dropped — the row's title already shows it"""
		text = "Name: CRM-LEAD-2025-00001 <br> Full Name : Jane Foster"

		self.assertEqual(_clean_excerpt(text), "Full Name : Jane Foster")

	def test_strips_converted_field(self):
		"""The raw "Converted : 0/1" field is dropped — already shown as a badge"""
		text = "Full Name : Jane Foster <br> Converted : 1"

		self.assertEqual(_clean_excerpt(text), "Full Name : Jane Foster")

	def test_strips_leading_name_field_when_match_highlights_the_label(self):
		"""frappe_search can highlight a match inside the label itself, e.g.
		searching "name" produces "<mark>Name</mark>: ..." — still recognised
		and dropped, not left behind as a bare unlabelled first line"""
		text = "<mark>Name</mark>: CRM-LEAD-2025-00001 <br> Full Name : Jane Foster"

		self.assertEqual(_clean_excerpt(text), "Full Name : Jane Foster")

	def test_strips_converted_field_when_match_highlights_the_label(self):
		"""Same highlighting case for the Converted field"""
		text = "Full Name : Jane Foster <br> <mark>Converted</mark> : 1"

		self.assertEqual(_clean_excerpt(text), "Full Name : Jane Foster")

	def test_leaves_other_fields_untouched(self):
		"""A field that isn't the leading Name or a Converted flag survives as-is"""
		text = "Full Name : Richard <mark>Foster</mark> <br> Organization : ChildAid Network"

		self.assertEqual(_clean_excerpt(text), text)
