import frappe
from frappe.tests import UnitTestCase

from frappe_crm_xt.api import gmail_linker as gl


class TestGmailLinker(UnitTestCase):
	def test_whole_address_only(self):
		self.assertTrue(gl._has_email_address(["a@x.com"], "x Al <a@x.com>, b@y.com None"))
		self.assertFalse(gl._has_email_address(["a@x.com"], "na@x.com a@x.com.au"))

	def test_rejects_non_string_args_via_whitelist_typing(self):
		for call in (
			lambda: gl.search_candidate_threads("CRM Deal", ["x"]),
			lambda: gl.search_by_subject(["x"], "CRM Deal", "x"),
			lambda: gl.get_thread_preview(["x"]),
		):
			self.assertRaises(frappe.FrappeTypeError, call)
