# Copyright (c) 2026, rtCamp and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_datetime, getdate

from frappe_crm_xt.tasks import deal_inactivity as di
from frappe_crm_xt.utils import holiday as hu

NOTIF = "CRM Slack — CRM Deal Inactivity (7 days)"
HL = "_Test DI Holidays"
# Holiday list marks Fri 2026-07-17 + the weekend 07-18/07-19 as non-working.
HOLIDAYS = ("2026-07-17", "2026-07-18", "2026-07-19")


class TestHolidayUtils(IntegrationTestCase):
	"""Pure working-day helpers (frappe_crm_xt.utils.holiday) — no DB needed."""

	def test_working_days_count(self):
		e = frozenset()
		self.assertEqual(hu.working_days_between("2026-01-01", "2026-01-08", e), 7)  # 7 days after
		self.assertEqual(hu.working_days_between("2026-01-01", "2026-01-01", e), 0)  # same day

	def test_working_days_excludes_holidays(self):
		hol = frozenset({getdate("2026-01-03"), getdate("2026-01-04")})
		self.assertEqual(hu.working_days_between("2026-01-01", "2026-01-08", hol), 5)  # 7 - 2

	def test_working_days_early_exit(self):
		# stops counting once it exceeds stop_at (cheap threshold tests)
		self.assertEqual(hu.working_days_between("2026-01-01", "2026-01-31", frozenset(), stop_at=3), 4)

	def test_is_non_working_day(self):
		hol = frozenset({getdate("2026-01-03")})
		self.assertTrue(hu.is_non_working_day("2026-01-03", hol))
		self.assertFalse(hu.is_non_working_day("2026-01-02", hol))
		self.assertFalse(hu.is_non_working_day("2026-01-02", frozenset()))

	def test_nth_working_day_back_no_holidays(self):
		# 6th working day back from 01-15 with no holidays == 01-10
		self.assertEqual(hu.nth_working_day_back("2026-01-15", 6, frozenset()), getdate("2026-01-10"))

	def test_nth_working_day_back_pushed_by_holidays(self):
		# holidays 01-12/01-13: working days back 15,14,11,10,09,08 → 6th = 01-08
		hol = frozenset({getdate("2026-01-12"), getdate("2026-01-13")})
		self.assertEqual(hu.nth_working_day_back("2026-01-15", 6, hol), getdate("2026-01-08"))

	def test_no_holiday_list_counts_every_day(self):
		# With an empty holiday set every day is a working day — nothing is skipped or deferred.
		e = frozenset()
		self.assertFalse(hu.is_non_working_day("2026-07-18", e))  # Sat, but no list → working
		self.assertEqual(hu.working_days_between("2026-07-15", "2026-07-22", e), 7)  # all 7 count
		self.assertEqual(
			hu.add_hours_deferred("2026-07-17 09:00:00", 24, e), get_datetime("2026-07-18 09:00:00")
		)  # Fri + 24h = Sat, no deferral

	def test_add_hours_deferred(self):
		hol = frozenset({getdate("2026-07-18"), getdate("2026-07-19")})
		# lands on a working day → returned as-is
		self.assertEqual(
			hu.add_hours_deferred("2026-07-20 10:00:00", 24, hol), get_datetime("2026-07-21 10:00:00")
		)
		# Fri 10:00 + 24h = Sat (holiday) → deferred to Mon, time preserved
		self.assertEqual(
			hu.add_hours_deferred("2026-07-17 10:00:00", 24, hol), get_datetime("2026-07-20 10:00:00")
		)
		# +48h = Sun (holiday) → still Mon
		self.assertEqual(
			hu.add_hours_deferred("2026-07-17 10:00:00", 48, hol), get_datetime("2026-07-20 10:00:00")
		)

	def test_cfg_inactive_days(self):
		self.assertEqual(di._cfg_inactive_days({}), di.DEFAULT_INACTIVE_DAYS)
		self.assertEqual(di._cfg_inactive_days({"deal_inactivity_days": 3}), 3)
		self.assertEqual(di._cfg_inactive_days({"deal_inactivity_days": 0}), di.DEFAULT_INACTIVE_DAYS)
		self.assertEqual(di._cfg_inactive_days({"deal_inactivity_days": "x"}), di.DEFAULT_INACTIVE_DAYS)


class TestNotifyInactiveDeals(IntegrationTestCase):
	"""Integration: notify_inactive_deals(as_of=...) — exact working-day crossing.
	IntegrationTestCase rolls back the DB after each test, so all setup is transient."""

	def setUp(self):
		self.owner = (
			frappe.db.get_value(
				"User",
				{"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]},
				"name",
			)
			or "Administrator"
		)

		if not frappe.db.exists("Holiday List", HL):
			hl = frappe.get_doc(
				{
					"doctype": "Holiday List",
					"holiday_list_name": HL,
					"from_date": "2026-06-01",
					"to_date": "2026-08-31",
				}
			)
			for d in HOLIDAYS:
				hl.append("holidays", {"holiday_date": d, "description": "t"})
			hl.insert(ignore_permissions=True)

		if not frappe.db.exists("Notification", NOTIF):
			frappe.get_doc(
				{
					"doctype": "Notification",
					"name": NOTIF,
					"subject": "{{ count }} inactive deals",
					"document_type": "CRM Deal",
					"event": "New",
					"channel": "System Notification",
					"message": "{{ doc.organization_name }}",
				}
			).insert(ignore_permissions=True)
		n = frappe.get_doc("Notification", NOTIF)
		n.enabled = 1
		n.slack_webhook_url = None  # no real Slack during tests
		n.condition_type = "Python"
		n.condition = '"_TESTDI" in (doc.organization_name or "")'  # scope to this test's deals
		if not n.message:
			n.message = "{{ doc.organization_name }}"
		n.save(ignore_permissions=True)

		s = frappe.get_single("CRM XT Settings")
		s.deal_inactivity_notification = NOTIF
		s.deal_inactivity_csm_notification = None  # settings are cached; keep tests independent
		s.deal_inactivity_days = 3  # 3 WORKING days
		s.deal_inactivity_use_company_holiday_list = 0
		s.deal_inactivity_holiday_list = HL  # these tests pin holidays to this list only
		s.deal_inactivity_followup_enabled = 1
		s.deal_inactivity_task_priority = "High"
		s.deal_inactivity_task_title = "_TESTDI: {{ doc.organization_name }}"
		s.deal_inactivity_task_body = "x"
		s.save(ignore_permissions=True)

	def _deal(self, org, modified):
		d = frappe.get_doc(
			{"doctype": "CRM Deal", "organization_name": org, "status": "Open", "deal_owner": self.owner}
		).insert(ignore_permissions=True)
		for t in frappe.get_all(
			"CRM Task", filters={"reference_doctype": "CRM Deal", "reference_docname": d.name}, pluck="name"
		):
			frappe.delete_doc("CRM Task", t, force=True, ignore_permissions=True, delete_permanently=True)
		frappe.db.set_value("CRM Deal", d.name, "modified", modified + " 10:00:00", update_modified=False)
		return d.name

	def _tasks(self, deal):
		return frappe.db.count(
			"CRM Task",
			{"reference_doctype": "CRM Deal", "reference_docname": deal, "title": ["like", "_TESTDI:%"]},
		)

	def test_flags_on_exact_working_day(self):
		# as_of Tue 2026-07-21, threshold 3 working days, holidays 07-17/18/19.
		alpha = self._deal("_TESTDI alpha", "2026-07-15")  # exactly 3 working days → flag
		gamma = self._deal("_TESTDI gamma", "2026-07-16")  # only 2 working days → no
		eps = self._deal("_TESTDI epsilon", "2026-07-10")  # already 8 working days (crossed earlier) → no
		di.notify_inactive_deals(as_of="2026-07-21")
		self.assertEqual(self._tasks(alpha), 1)
		self.assertEqual(self._tasks(gamma), 0)
		self.assertEqual(self._tasks(eps), 0)

	def test_flags_only_on_the_crossing_day(self):
		# eps last active 07-10; with these holidays its 3rd working day is 07-13.
		eps = self._deal("_TESTDI cross", "2026-07-10")
		di.notify_inactive_deals(as_of="2026-07-12")  # 2 working days → not yet
		self.assertEqual(self._tasks(eps), 0)
		di.notify_inactive_deals(as_of="2026-07-13")  # exactly 3 → flag
		self.assertEqual(self._tasks(eps), 1)
		di.notify_inactive_deals(as_of="2026-07-14")  # now 4 working days → not again
		self.assertEqual(self._tasks(eps), 1)

	def test_holiday_dense_span_still_caught_without_buffer(self):
		# Fri→Tue across a holiday + weekend: exact window absorbs the non-working days.
		d = self._deal("_TESTDI dense", "2026-07-16")  # 3rd working day = 07-22 (07-17/18/19 skipped)
		di.notify_inactive_deals(as_of="2026-07-22")
		self.assertEqual(self._tasks(d), 1)

	def test_skips_when_run_day_is_a_holiday(self):
		# reaches 3 working days as of 07-17, but 07-17 is a holiday → skipped
		d = self._deal("_TESTDI onhol", "2026-07-13")
		di.notify_inactive_deals(as_of="2026-07-17")
		self.assertEqual(self._tasks(d), 0)

	def test_dedup_across_runs(self):
		self._deal("_TESTDI dedup", "2026-07-15")
		di.notify_inactive_deals(as_of="2026-07-21")
		di.notify_inactive_deals(as_of="2026-07-21")
		self.assertEqual(frappe.db.count("CRM Task", {"title": ["like", "_TESTDI: _TESTDI dedup%"]}), 1)

	def test_off_when_no_notification(self):
		s = frappe.get_single("CRM XT Settings")
		s.deal_inactivity_notification = None
		s.save(ignore_permissions=True)
		alpha = self._deal("_TESTDI off", "2026-07-15")
		res = di.notify_inactive_deals(as_of="2026-07-21")
		self.assertEqual(res["deals_notified"], 0)
		self.assertEqual(res["reason"], "no notification selected")
		self.assertEqual(self._tasks(alpha), 0)

	def test_csm_notification_runs_on_its_own(self):
		s = frappe.get_single("CRM XT Settings")
		s.deal_inactivity_notification = None
		s.deal_inactivity_csm_notification = NOTIF
		s.save(ignore_permissions=True)
		alpha = self._deal("_TESTDI csm", "2026-07-15")
		res = di.notify_inactive_deals(as_of="2026-07-21")
		self.assertEqual(res["deals_notified"], 1)
		self.assertEqual(self._tasks(alpha), 1)
