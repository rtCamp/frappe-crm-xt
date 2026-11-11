# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

import unittest

import frappe
from frappe.tests import IntegrationTestCase

from frappe_crm_xt.doc_events.lead_deal_delete import on_trash

# on_trash touches the "Gmail Thread" doctype, which ships with the optional
# frappe_gmail_thread app. That app is not a declared dependency (hooks.py only
# requires "crm"), so skip these tests when it is not installed.
_GMAIL_THREAD_INSTALLED = "frappe_gmail_thread" in frappe.get_installed_apps()


@unittest.skipUnless(
	_GMAIL_THREAD_INSTALLED,
	"frappe_gmail_thread app (Gmail Thread doctype) is not installed",
)
class TestLeadDealDelete(IntegrationTestCase):
	def test_on_trash_removes_contact_dynamic_link(self):
		"""on_trash drops the Contact -> CRM Deal Dynamic Link row but keeps the Contact"""
		token = frappe.generate_hash(length=8)

		deal = frappe.get_doc({"doctype": "CRM Deal"}).insert(ignore_permissions=True)
		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": f"XT-LinkedContact-{token}",
				"links": [{"link_doctype": "CRM Deal", "link_name": deal.name}],
			}
		).insert(ignore_permissions=True)

		# Sanity: the dynamic link row exists
		self.assertTrue(
			frappe.db.exists(
				"Dynamic Link",
				{
					"parenttype": "Contact",
					"parent": contact.name,
					"link_doctype": "CRM Deal",
					"link_name": deal.name,
				},
			)
		)

		on_trash(frappe._dict(doctype="CRM Deal", name=deal.name))

		# Dynamic Link row gone, Contact still present
		self.assertFalse(
			frappe.db.exists(
				"Dynamic Link",
				{
					"parenttype": "Contact",
					"parent": contact.name,
					"link_doctype": "CRM Deal",
					"link_name": deal.name,
				},
			)
		)
		self.assertTrue(frappe.db.exists("Contact", contact.name))

	def test_on_trash_for_doc_with_no_links(self):
		"""on_trash runs without error when no Dynamic Link rows reference the doc"""
		on_trash(frappe._dict(doctype="CRM Deal", name=f"XT-Deal-Nope-{frappe.generate_hash(length=8)}"))

	def test_on_trash_leaves_other_links_alone(self):
		"""on_trash only removes back-references for THIS doc, not other dynamic links on the same Contact"""
		token = frappe.generate_hash(length=8)

		deal_a = frappe.get_doc({"doctype": "CRM Deal"}).insert(ignore_permissions=True)
		deal_b = frappe.get_doc({"doctype": "CRM Deal"}).insert(ignore_permissions=True)
		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": f"XT-MultiContact-{token}",
				"links": [
					{"link_doctype": "CRM Deal", "link_name": deal_a.name},
					{"link_doctype": "CRM Deal", "link_name": deal_b.name},
				],
			}
		).insert(ignore_permissions=True)

		on_trash(frappe._dict(doctype="CRM Deal", name=deal_a.name))

		self.assertFalse(
			frappe.db.exists(
				"Dynamic Link",
				{"parent": contact.name, "link_doctype": "CRM Deal", "link_name": deal_a.name},
			)
		)
		self.assertTrue(
			frappe.db.exists(
				"Dynamic Link",
				{"parent": contact.name, "link_doctype": "CRM Deal", "link_name": deal_b.name},
			)
		)
