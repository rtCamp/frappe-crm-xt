# Copyright (c) 2026, rtCamp and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# Sanity bounds (not business limits) — guard against typos like 5000 / 100000.
MAX_INACTIVITY_DAYS = 365
MAX_INCOMING_HOURS = 2160  # 90 days, in hours


class CRMXTSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		deal_inactivity_csm_notification: DF.Link | None
		deal_inactivity_days: DF.Int
		deal_inactivity_followup_enabled: DF.Check
		deal_inactivity_holiday_list: DF.Link | None
		deal_inactivity_notification: DF.Link | None
		deal_inactivity_task_body: DF.TextEditor | None
		deal_inactivity_task_priority: DF.Literal["Low", "Medium", "High"]
		deal_inactivity_task_title: DF.Data | None
		deal_inactivity_use_company_holiday_list: DF.Check
		incoming_alert_enabled: DF.Check
		incoming_alert_hours: DF.Int
	# end: auto-generated types

	def validate(self):
		if (self.deal_inactivity_days or 0) > MAX_INACTIVITY_DAYS:
			frappe.throw(
				_(
					"Inactivity After (Working Days) can be at most {0} (leave blank for the default of 7)."
				).format(MAX_INACTIVITY_DAYS)
			)
		if (self.incoming_alert_hours or 0) > MAX_INCOMING_HOURS:
			frappe.throw(
				_(
					"Unanswered After (Hours) can be at most {0} (90 days); leave blank for the default of 24."
				).format(MAX_INCOMING_HOURS)
			)
