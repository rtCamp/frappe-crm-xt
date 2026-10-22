from datetime import datetime

import frappe


def _collect_emails(doctype: str, docname: str) -> list[str]:
	doc = frappe.get_doc(doctype, docname)
	emails: set[str] = set()
	if getattr(doc, "email", None):
		emails.add(doc.email.strip().lower())
	for row in getattr(doc, "contacts", []) or []:
		if getattr(row, "email", None):
			emails.add(row.email.strip().lower())
	return [e for e in emails if e]


def _short_recipients(raw: str | None, keep: int = 3) -> str:
	if not raw:
		return ""
	parts = [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]
	if len(parts) <= keep:
		return ", ".join(parts)
	return ", ".join(parts[:keep]) + f" +{len(parts) - keep} more"


THREAD_FIELDS = [
	"name",
	"subject_of_first_mail",
	"gmail_thread_id",
	"reference_doctype",
	"reference_name",
	"gmail_account",
]
MAX_THREADS = 20


def _matching_thread_ids(emails: list[str]) -> list[str]:
	e = frappe.qb.DocType("Single Email CT")
	match = None
	for addr in emails:
		cond = (e.sender == addr) | e.recipients.like(f"%{addr}%") | e.cc.like(f"%{addr}%")
		match = cond if match is None else (match | cond)
	return frappe.qb.from_(e).select(e.parent).distinct().where(match).run(pluck=True)


def _with_thread_stats(threads: list[dict]) -> list[dict]:
	"""Add whole-thread message count and last message time, the Gmail button flag, newest first."""
	if not threads:
		return []

	stats = {
		r.parent: r
		for r in frappe.get_all(
			"Single Email CT",
			filters={"parent": ["in", [t.name for t in threads]]},
			fields=[
				"parent",
				{"COUNT": "name", "as": "num_emails"},
				{"MAX": "date_and_time", "as": "last_email_on"},
			],
			group_by="parent",
		)
	}
	own_account = frappe.get_value("Gmail Account", {"linked_user": frappe.session.user})
	for t in threads:
		stat = stats.get(t.name)
		t["num_emails"] = stat.num_emails if stat else 0
		t["last_email_on"] = stat.last_email_on if stat else None
		account = t.pop("gmail_account")
		t["can_open_gmail"] = int(bool(own_account) and account == own_account)
	return sorted(threads, key=lambda t: t["last_email_on"] or datetime.min, reverse=True)[:MAX_THREADS]


def _get_threads(filters: dict) -> list[dict]:
	# get_list applies Gmail Thread read permission in SQL, so the limit is applied after it.
	return frappe.get_list(
		"Gmail Thread",
		fields=THREAD_FIELDS,
		filters=filters,
		order_by="modified desc",
		limit_page_length=MAX_THREADS,
	)


@frappe.whitelist()
def search_candidate_threads(doctype: str, docname: str):
	"""Threads involving any of this record's emails that are unlinked or linked to this record."""
	if doctype not in ["CRM Lead", "CRM Deal"]:
		return []

	frappe.has_permission(doctype, "read", doc=docname, throw=True)

	emails = _collect_emails(doctype, docname)
	ids = _matching_thread_ids(emails) if emails else []
	if not ids:
		return []

	return _with_thread_stats(_get_threads({"name": ["in", ids], "reference_name": ["in", ["", docname]]}))


@frappe.whitelist()
def search_by_subject(query: str, doctype: str, docname: str):
	"""Explicit subject search across Gmail Threads unlinked or linked here,
	regardless of the record's emails. Shape matches search_candidate_threads."""
	query = (query or "").strip()
	if not query or doctype not in ("CRM Lead", "CRM Deal"):
		return []
	frappe.has_permission(doctype, "read", doc=docname, throw=True)

	threads = _get_threads(
		{"subject_of_first_mail": ["like", f"%{query}%"], "reference_name": ["in", ["", docname]]}
	)
	return _with_thread_stats(threads)


@frappe.whitelist()
def get_thread_preview(name: str):
	"""Preview: subject + last few emails with sanitized HTML body and
	compacted recipients. HTML is sanitized server-side so the frontend can
	render it directly."""
	frappe.has_permission("Gmail Thread", "read", doc=name, throw=True)
	thread = frappe.get_doc("Gmail Thread", name)
	emails = []
	for e in (thread.emails or [])[-10:]:
		emails.append(
			{
				"sender": e.sender,
				"sender_full_name": e.sender_full_name,
				"recipients_short": _short_recipients(e.recipients),
				"subject": e.subject,
				"creation": e.date_and_time,
				"html": frappe.utils.sanitize_html(e.content or ""),
				"sent_or_received": e.sent_or_received,
			}
		)
	return {
		"name": thread.name,
		"subject": thread.subject_of_first_mail,
		"gmail_thread_id": thread.gmail_thread_id,
		"emails": emails,
	}
