import frappe
from frappe.tests import IntegrationTestCase

from frappe_crm_xt.patches.v1_0.add_crm_pipeline_and_csm_notifications import migrate_pipelines


class TestPipelinePatch(IntegrationTestCase):
	def _deal(self, value):
		d = frappe.get_doc({"doctype": "CRM Deal", "organization_name": "_TESTPL", "status": "Open"})
		d.insert(ignore_permissions=True, ignore_links=True)
		# raw write: the patch runs on legacy free-text values that Link validation would reject
		frappe.db.set_value("CRM Deal", d.name, "custom_pipeline", value, update_modified=False)
		return d.name

	def test_every_value_gets_a_pipeline_without_touching_modified(self):
		names = [
			self._deal(v)
			for v in ("Renewals ", "renewal", "Easy Engine", "Odd One ", "Odd One", "", "   ", None)
		]
		before = {n: frappe.db.get_value("CRM Deal", n, "modified") for n in names}
		migrate_pipelines()
		got = [frappe.db.get_value("CRM Deal", n, "custom_pipeline") for n in names]
		self.assertEqual(got, ["Renewals", "Renewals", "EasyEngine", "Odd One", "Odd One", None, None, None])
		self.assertEqual(before, {n: frappe.db.get_value("CRM Deal", n, "modified") for n in names})
		self.assertEqual(frappe.db.get_value("CRM Pipeline", "Renewals", "is_csm"), 1)
		migrate_pipelines()  # safe to re-run
		self.assertEqual(got, [frappe.db.get_value("CRM Deal", n, "custom_pipeline") for n in names])
