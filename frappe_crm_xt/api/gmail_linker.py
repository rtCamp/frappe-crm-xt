import re
from datetime import datetime

import frappe
from frappe.utils import add_days, now_datetime
from pypika.terms import Criterion


def _collect_email_addresses(doctype: str, docname: str) -> list[str]:
	"""Email addresses of the record and of its contacts, lowercased."""
	record = frappe.get_doc(doctype, docname)
	people = [record, *(record.get("contacts") or [])]
	return list({(person.get("email") or "").strip().lower() for person in people} - {""})


def _short_recipients(raw_recipients: str | None, keep: int = 3) -> str:
	if not raw_recipients:
		return ""
	recipients = [r.strip() for r in raw_recipients.replace("\n", ",").split(",") if r.strip()]
	if len(recipients) <= keep:
		return ", ".join(recipients)
	return ", ".join(recipients[:keep]) + f" +{len(recipients) - keep} more"


THREAD_FIELDS = [
	"name",
	"subject_of_first_mail",
	"gmail_thread_id",
	"reference_doctype",
	"reference_name",
]
MAX_THREADS = 20


def _matching_thread_names(email_addresses: list[str]) -> list[str]:
	"""Names of recent Gmail Threads where one of `email_addresses` is sender/recipient/cc as a whole address."""
	if not email_addresses:
		return []
	single_email = frappe.qb.DocType("Single Email CT")
	involves_email_address = Criterion.any(
		[
			(single_email.sender == email_address)
			| single_email.recipients.like(f"%{email_address}%")
			| single_email.cc.like(f"%{email_address}%")
			for email_address in email_addresses
		]
	)
	recent_emails = (
		frappe.qb.from_(single_email)
		.select(single_email.parent, single_email.sender, single_email.recipients, single_email.cc)
		.where(involves_email_address & (single_email.date_and_time >= add_days(now_datetime(), -365)))
		.orderby(single_email.date_and_time, order=frappe.qb.desc)
		.limit(500)
		.run(as_dict=True)
	)
	return list(
		{
			email.parent
			for email in recent_emails
			if _has_email_address(email_addresses, f"{email.sender} {email.recipients} {email.cc}")
		}
	)


def _has_email_address(email_addresses: list[str], text: str) -> bool:
	"""True if any of `email_addresses` appears as a whole address (LIKE alone matches a@x.com inside na@x.com)."""
	pattern = r"(?<![\w.+-])(?:%s)(?![\w-]|\.\w)" % "|".join(map(re.escape, email_addresses))
	return re.search(pattern, text, re.I) is not None


def _with_thread_stats(threads: list[dict]) -> list[dict]:
	"""Add whole-thread message count and last message time, newest first."""
	stats_by_thread = {
		stats.parent: stats
		for stats in frappe.get_all(
			"Single Email CT",
			filters={"parent": ["in", [thread.name for thread in threads]]},
			fields=[
				"parent",
				{"COUNT": "name", "as": "num_emails"},
				{"MAX": "date_and_time", "as": "last_email_on"},
			],
			group_by="parent",
		)
	}
	for thread in threads:
		stats = stats_by_thread.get(thread.name) or frappe._dict(num_emails=0, last_email_on=None)
		thread.update(num_emails=stats.num_emails, last_email_on=stats.last_email_on)
	return sorted(threads, key=lambda thread: thread["last_email_on"] or datetime.min, reverse=True)[
		:MAX_THREADS
	]


def _get_threads(filters: dict) -> list[dict]:
	# get_list applies Gmail Thread read permission in SQL. Over-fetch candidates;
	# _with_thread_stats sorts by last email and trims to MAX_THREADS.
	return frappe.get_list(
		"Gmail Thread",
		fields=THREAD_FIELDS,
		filters=filters,
		order_by="modified desc",
		limit_page_length=200,
	)


def _can_read(doctype: str, docname: str) -> bool:
	"""Only CRM Lead/Deal are supported; raises if the user can't read the record."""
	if doctype not in ("CRM Lead", "CRM Deal"):
		return False
	frappe.has_permission(doctype, "read", doc=docname, throw=True)
	return True


@frappe.whitelist()
def is_available() -> bool:
	return "frappe_gmail_thread" in frappe.get_installed_apps()


@frappe.whitelist()
def search_candidate_threads(doctype: str, docname: str):
	"""Threads involving any of this record's emails that are unlinked or linked to this record."""
	if not _can_read(doctype, docname):
		return []

	thread_names = _matching_thread_names(_collect_email_addresses(doctype, docname))
	unlinked_or_here = _get_threads({"name": ["in", thread_names], "reference_name": ["in", ["", docname]]})
	linked_here = _get_threads({"reference_doctype": doctype, "reference_name": docname})
	# Already-linked threads stay listed even if they no longer match the record's email addresses.
	threads_by_name = {thread.name: thread for thread in unlinked_or_here + linked_here}
	return _with_thread_stats(list(threads_by_name.values()))


@frappe.whitelist()
def search_by_subject(query: str, doctype: str, docname: str):
	"""Explicit subject search across Gmail Threads unlinked or linked here,
	regardless of the record's emails. Shape matches search_candidate_threads."""
	query = query.strip()
	if not query or not _can_read(doctype, docname):
		return []

	threads = _get_threads({"all_subjects": ["like", f"%{query}%"], "reference_name": ["in", ["", docname]]})
	return _with_thread_stats(threads)


@frappe.whitelist()
def get_thread_preview(name: str):
	"""Preview: subject + last few emails with sanitized HTML body and
	compacted recipients. HTML is sanitized server-side so the frontend can
	render it directly."""
	frappe.has_permission("Gmail Thread", "read", doc=name, throw=True)
	thread = frappe.get_doc("Gmail Thread", name)
	emails = []
	for email in (thread.emails or [])[-10:]:
		emails.append(
			{
				"sender": email.sender,
				"sender_full_name": email.sender_full_name,
				"recipients_short": _short_recipients(email.recipients),
				"subject": email.subject,
				"creation": email.date_and_time,
				"html": frappe.utils.sanitize_html(email.content or ""),
				"sent_or_received": email.sent_or_received,
			}
		)
	return {
		"name": thread.name,
		"subject": thread.subject_of_first_mail,
		"gmail_thread_id": thread.gmail_thread_id,
		"emails": emails,
	}
