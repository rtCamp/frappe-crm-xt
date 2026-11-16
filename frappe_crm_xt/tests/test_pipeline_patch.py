import frappe
from frappe.tests import IntegrationTestCase

from frappe_crm_xt.patches.v1_0.add_crm_pipeline_and_csm_notifications import (
	migrate_pipelines,
	split_notifications,
)


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
		migrate_pipelines()  # safe to re-run
		self.assertEqual(got, [frappe.db.get_value("CRM Deal", n, "custom_pipeline") for n in names])


class TestSplitNotifications(IntegrationTestCase):
	NAME = "CRM Slack — CRM Deal Inactivity (7 days)"

	def _sales(self, condition, condition_type="Python"):
		frappe.delete_doc("Notification", self.NAME + " (CSM)", force=True, ignore_permissions=True)
		if not frappe.db.exists("Notification", self.NAME):
			frappe.get_doc(
				{
					"doctype": "Notification",
					"name": self.NAME,
					"subject": "x",
					"document_type": "CRM Deal",
					"event": "Custom",
					"channel": "System Notification",
					"message": "x",
				}
			).insert(ignore_permissions=True)
		n = frappe.get_doc("Notification", self.NAME)
		n.condition_type, n.condition, n.filters = (
			condition_type,
			condition,
			None,
		)  # tests share one transaction
		n.save(ignore_permissions=True)

	def _conditions(self):
		get = frappe.db.get_value
		return get("Notification", self.NAME, "condition"), get(
			"Notification", self.NAME + " (CSM)", "condition"
		)

	def test_old_renewal_rule_is_replaced(self):
		self._sales("'renewal' not in (doc.custom_pipeline or '').lower()")
		split_notifications()
		self.assertEqual(
			self._conditions(),
			(
				"'renewal' not in (doc.custom_pipeline or '').lower()",
				"'renewal' in (doc.custom_pipeline or '').lower()",
			),
		)

	def test_custom_condition_is_kept_in_both_and_rerun_changes_nothing(self):
		self._sales('doc.status == "Open"')
		split_notifications()
		first = self._conditions()
		self.assertEqual(
			first[0], "(doc.status == \"Open\") and 'renewal' not in (doc.custom_pipeline or '').lower()"
		)
		self.assertEqual(
			first[1], "(doc.status == \"Open\") and 'renewal' in (doc.custom_pipeline or '').lower()"
		)
		split_notifications()
		self.assertEqual(self._conditions(), first)

	def test_filters_mode_without_filters_becomes_python(self):
		self._sales(None, condition_type="Filters")
		split_notifications()
		self.assertEqual(frappe.db.get_value("Notification", self.NAME, "condition_type"), "Python")
		self.assertEqual(
			frappe.db.get_value("Notification", self.NAME + " (CSM)", "condition_type"), "Python"
		)

	def test_unrecognised_renewal_rule_is_skipped(self):
		old = "doc.a or 'Renewal' not in (doc.custom_pipeline or '')"
		self._sales(old)
		split_notifications()
		self.assertEqual(self._conditions(), (old, None))

	def test_filters_mode_with_filters_is_skipped(self):
		self._sales(None, condition_type="Filters")
		frappe.db.set_value("Notification", self.NAME, "filters", '[["CRM Deal","status","=","Open"]]')
		split_notifications()
		self.assertEqual(frappe.db.get_value("Notification", self.NAME, "condition_type"), "Filters")
		self.assertFalse(frappe.db.exists("Notification", self.NAME + " (CSM)"))
