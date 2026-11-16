import json
import re

import frappe
from frappe.utils import add_days, get_datetime, getdate, nowdate

from frappe_crm_xt.utils import holiday as hu

SETTINGS = "CRM XT Settings"

# Defaults for blank CRM XT Settings fields.
DEFAULT_INACTIVE_DAYS = 7  # working days
DEFAULT_CLOSED_STATUSES = ("Won", "Lost")
DEFAULT_TASK_TITLE = "Follow up on inactive deal"
DEFAULT_TASK_PRIORITY = "High"

# Slack message size cap + the message template's comment-divider syntax.
SLACK_TEXT_LIMIT = 38000
BLOCK_SEPARATOR = "\n\n"
COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)


def _skipped(reason):
	"""Consistent 'nothing sent' result — notify_inactive_deals always returns this shape."""
	return {"candidates": 0, "deals_notified": 0, "messages": 0, "reason": reason}


def notify_inactive_deals(as_of=None):
	"""Scheduler entry (daily); runs once per Notification selected in CRM XT Settings (sales and CSM).
	Always returns a dict: {candidates, deals_notified, messages, reason} (counts summed over both).

	`as_of` ("YYYY-MM-DD") overrides today for backfill/tests; the scheduler passes none.
	"""
	if not frappe.db.exists("DocType", SETTINGS):
		return _skipped("settings doctype missing")
	settings = frappe.get_cached_doc(SETTINGS)

	# dict.fromkeys: the same Notification picked in both fields must not post twice
	names = dict.fromkeys(
		settings.get(f) for f in ("deal_inactivity_notification", "deal_inactivity_csm_notification")
	)
	results = [_notify_one(settings, n, as_of) for n in names if n] or [_skipped("no notification selected")]
	counts = {k: sum(r[k] for r in results) for k in ("candidates", "deals_notified", "messages")}
	reason = "ok" if any(r["reason"] == "ok" for r in results) else results[0]["reason"]
	return {**results[0], **counts, "reason": reason}


def _notify_one(settings, notification_name, as_of):
	if not frappe.db.exists("Notification", notification_name):
		return _skipped("no notification selected")
	notification = frappe.get_doc("Notification", notification_name)
	if not notification.enabled:
		return _skipped("notification disabled")

	threshold = _cfg_inactive_days(settings)  # working days
	closed_statuses = DEFAULT_CLOSED_STATUSES
	followup_enabled = bool(settings.get("deal_inactivity_followup_enabled"))
	use_company_hl = bool(settings.get("deal_inactivity_use_company_holiday_list"))
	fixed_hl = settings.get("deal_inactivity_holiday_list")
	title_tmpl = settings.get("deal_inactivity_task_title")
	body_tmpl = settings.get("deal_inactivity_task_body")
	priority = settings.get("deal_inactivity_task_priority") or DEFAULT_TASK_PRIORITY

	today = as_of or nowdate()

	prefetch_start = add_days(today, -(threshold + hu.MAX_LOOKBACK))
	holidays = hu.holiday_dates(hu.resolve_holiday_list(use_company_hl, fixed_hl), prefetch_start, today)
	if hu.is_non_working_day(today, holidays):
		return _skipped("today is a holiday")

	high_day = add_days(today, -threshold)
	low_date = hu.nth_working_day_back(today, threshold + 1, holidays)
	day = [f"{low_date} 00:00:00", f"{getdate(high_day)} 23:59:59"]

	deal_meta = frappe.get_meta("CRM Deal")
	date_fields = [
		f for f in ("last_responded_on", "custom_last_incoming_email_time") if deal_meta.has_field(f)
	]
	or_filters = {"modified": ["between", day]}
	for f in date_fields:
		or_filters[f] = ["between", day]

	# Notes/tasks/comments don't bump deal.modified, so gather from every source.
	candidates = set(
		frappe.get_all(
			"CRM Deal",
			filters={"status": ["not in", closed_statuses]},
			or_filters=or_filters,
			pluck="name",
		)
	)
	candidates |= _deals_touched_on("FCRM Note", "reference_docname", "modified", day)
	candidates |= _deals_touched_on("CRM Task", "reference_docname", "modified", day)
	candidates |= _deals_touched_on("Comment", "reference_name", "creation", day, comment_type="Comment")
	if not candidates:
		return _skipped("no candidates in window")

	names = list(candidates)
	fields = ["name", "modified", *date_fields]
	deals = frappe.get_all(
		"CRM Deal",
		filters={"name": ["in", names], "status": ["not in", closed_statuses]},
		fields=fields,
	)
	notes = _latest_map("FCRM Note", "reference_docname", "modified", names)
	tasks = _latest_map("CRM Task", "reference_docname", "modified", names)
	comments = _latest_map("Comment", "reference_name", "creation", names, comment_type="Comment")

	blocks = []
	for d in deals:
		stamps = [d.modified, notes.get(d.name), tasks.get(d.name), comments.get(d.name)]
		stamps += [d.get(f) for f in date_fields]
		last = max(get_datetime(s) for s in stamps if s)

		if hu.working_days_between(last, today, holidays, stop_at=threshold) != threshold:
			continue  # only on the exact day the streak reaches `threshold` working days
		try:
			deal = frappe.get_doc("CRM Deal", d.name)
			deal.last_activity_on = last  # transient, surfaced in the message
			if not _passes_notification_condition(notification, deal):
				continue
			title = _render_task_field(title_tmpl, deal, threshold) or DEFAULT_TASK_TITLE
			if _followup_exists(deal.name, title, last):
				continue  # streak already handled
			block = _render_message(
				notification, deal, threshold
			)  # render before side effects (no orphan task on a bad template)
			if followup_enabled:
				_create_followup_task(deal, title, _render_task_field(body_tmpl, deal, threshold), priority)
			blocks.append(block)
		except Exception:
			frappe.log_error(
				title="Deal inactivity alert failed",
				message=f"Deal: {d.name}\n\n{frappe.get_traceback()}",
			)

	if not blocks:
		return {
			"candidates": len(deals),
			"deals_notified": 0,
			"messages": 0,
			"reason": "no deals crossed threshold",
		}

	# Digest needs a webhook; follow-up tasks are created regardless.
	messages = _send_slack_digest(notification, blocks, threshold) if notification.slack_webhook_url else 0
	return {"candidates": len(deals), "deals_notified": len(blocks), "messages": messages, "reason": "ok"}


def _render_message(notification, deal, days):
	"""Render the Notification's message template for one deal (same context as .send(), plus
	`days` = the inactivity threshold)."""
	from frappe.email.doctype.notification.notification import get_context

	context = get_context(deal)
	context.update({"alert": notification, "comments": None, "days": days})
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
	return frappe.render_template(notification.message, context)


def _send_slack_digest(notification, blocks, threshold):
	"""Post the blocks under one header, splitting into more messages only past the size cap."""
	from frappe.integrations.doctype.slack_webhook_url.slack_webhook_url import send_slack_message

	# First message-comment supplies the block divider (\n unescaped); comments are stripped.
	separator = BLOCK_SEPARATOR
	for b in blocks:
		m = COMMENT_RE.search(b)
		if m:
			separator = m.group(1).replace("\\n", "\n")
			break
	blocks = [COMMENT_RE.sub("", b).strip() for b in blocks]

	n = len(blocks)
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
	header = frappe.render_template(notification.subject or "", {"count": n, "days": threshold})

	posts, current = [], None
	for block in blocks:
		if current is None:
			current = f"{header}\n\n{block}"
			continue
		candidate = current + separator + block
		if len(candidate) > SLACK_TEXT_LIMIT:
			posts.append(current)
			current = f"{header}\n\n{block}"
		else:
			current = candidate
	if current is not None:
		posts.append(current)

	for post in posts:
		send_slack_message(
			webhook_url=notification.slack_webhook_url,
			message=post,
			reference_doctype="CRM Deal",
			reference_name=None,
		)
	return len(posts)


def _passes_notification_condition(notification, deal):
	"""Honor the Notification's own Condition/Filters (which .send() itself does not)."""
	from frappe.email.doctype.notification.notification import get_context
	from frappe.utils.data import evaluate_filters

	if notification.condition_type == "Python" and notification.condition:
		return bool(frappe.safe_eval(notification.condition, None, get_context(deal)))
	if notification.condition_type == "Filters" and notification.filters:
		return evaluate_filters(deal, json.loads(notification.filters))
	return True


def _cfg_inactive_days(settings):
	"""Working-day threshold; DEFAULT_INACTIVE_DAYS when blank."""
	try:
		days = int(settings.get("deal_inactivity_days") or 0)
	except (TypeError, ValueError):
		days = 0
	return days if days > 0 else DEFAULT_INACTIVE_DAYS


def _followup_exists(deal_name, title, last):
	"""Whether a same-title follow-up task exists for this streak (created since `last`)."""
	return bool(
		frappe.get_all(
			"CRM Task",
			filters={
				"reference_doctype": "CRM Deal",
				"reference_docname": deal_name,
				"title": title,
				"creation": [">=", get_datetime(last)],
			},
			limit=1,
			ignore_permissions=True,
		)
	)


def _create_followup_task(deal, title, body, priority):
	"""Plain follow-up CRM Task — no dates/calendar fields, so never a calendar task."""
	frappe.get_doc(
		{
			"doctype": "CRM Task",
			"title": title,
			"description": body or None,
			"reference_doctype": "CRM Deal",
			"reference_docname": deal.name,
			"assigned_to": deal.get("deal_owner") or None,
			"status": "Todo",
			"priority": priority,
		}
	).insert(ignore_permissions=True)


def _render_task_field(template, deal, days):
	"""Render an admin-authored Jinja title/body template against the deal, with `days` = the
	inactivity threshold available in context."""
	if not template:
		return ""
	from frappe.email.doctype.notification.notification import get_context

	context = get_context(deal)
	context["days"] = days
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
	return frappe.render_template(template, context)


def _deals_touched_on(doctype, ref_field, date_field, day, comment_type=None):
	"""CRM Deal names with a note/task/comment dated within the `day` window."""
	filters = {
		"reference_doctype": "CRM Deal",
		ref_field: ["is", "set"],
		date_field: ["between", day],
	}
	if comment_type:
		filters["comment_type"] = comment_type
	return set(frappe.get_all(doctype, filters=filters, pluck=ref_field))


def _latest_map(doctype, ref_field, date_field, deal_names, comment_type=None):
	"""{deal: latest activity timestamp} across the given deals — one grouped query."""
	if not deal_names:
		return {}
	from frappe.query_builder.functions import Max

	t = frappe.qb.DocType(doctype)
	q = (
		frappe.qb.from_(t)
		.select(t[ref_field].as_("ref"), Max(t[date_field]).as_("ts"))
		.where(t.reference_doctype == "CRM Deal")
		.where(t[ref_field].isin(deal_names))
	)
	if comment_type:
		q = q.where(t.comment_type == comment_type)
	q = q.groupby(t[ref_field])
	return {r.ref: r.ts for r in q.run(as_dict=True) if r.ref}
