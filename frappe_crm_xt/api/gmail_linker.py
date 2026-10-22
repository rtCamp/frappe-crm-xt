import frappe
from frappe.query_builder import Case
from frappe.query_builder.functions import Count, Max


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


@frappe.whitelist()
def search_candidate_threads(doctype: str, docname: str):
	"""Search for Gmail threads linked to a given doctype/docname or any of its emails."""
	if doctype not in ["CRM Lead", "CRM Deal"]:
		return []

	frappe.has_permission(doctype, "read", doc=docname, throw=True)
	emails = _collect_emails(doctype, docname)
	if not emails:
		return []

	user = frappe.session.user
	t = frappe.qb.DocType("Gmail Thread")
	e = frappe.qb.DocType("Single Email CT")
	ga = frappe.qb.DocType("Gmail Account")

	match = None
	for addr in emails:
		cond = (e.sender == addr) | e.recipients.like(f"%{addr}%") | e.cc.like(f"%{addr}%")
		match = cond if match is None else (match | cond)

	linked_filter = (
		t.reference_name.isnull()
		| (t.reference_name == "")
		| ((t.reference_doctype == doctype) & (t.reference_name == docname))
	)

	last_email_on = Max(e.creation).as_("last_email_on")
	rows = (
		frappe.qb.from_(t)
		.inner_join(e)
		.on(e.parent == t.name)
		.left_join(ga)
		.on(ga.name == t.gmail_account)
		.select(
			t.name,
			t.subject_of_first_mail,
			t.gmail_thread_id,
			t.reference_doctype,
			t.reference_name,
			last_email_on,
			Count(e.name).as_("num_emails"),
			Case().when(ga.linked_user == user, 1).else_(0).as_("can_open_gmail"),
		)
		.where(match & linked_filter)
		.groupby(t.name)
		.orderby(Max(e.creation), order=frappe.qb.desc)
		.limit(50)
	).run(as_dict=True)
	return [r for r in rows if frappe.has_permission("Gmail Thread", "read", doc=r["name"])]


@frappe.whitelist()
def search_by_subject(query: str, doctype: str, docname: str):
	"""Explicit subject search across Gmail Threads unlinked or linked here,
	regardless of the record's emails. Shape matches search_candidate_threads."""
	query = (query or "").strip()
	if not query or doctype not in ("CRM Lead", "CRM Deal"):
		return []
	frappe.has_permission(doctype, "read", doc=docname, throw=True)

	like = f"%{query}%"
	# get_list applies Gmail Thread read permission, so no per-row check is needed.
	threads = frappe.get_list(
		"Gmail Thread",
		fields=[
			"name",
			"subject_of_first_mail",
			"gmail_thread_id",
			"reference_doctype",
			"reference_name",
			"gmail_account",
		],
		or_filters=[["subject_of_first_mail", "like", like]],
		order_by="modified desc",
		limit_page_length=50,
		distinct=True,
	)
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
				{"MAX": "creation", "as": "last_email_on"},
			],
			group_by="parent",
		)
	}
	own_account = frappe.get_value("Gmail Account", {"linked_user": frappe.session.user})
	for t in threads:
		t["num_emails"] = stats[t.name].num_emails if t.name in stats else 0
		t["last_email_on"] = stats[t.name].last_email_on if t.name in stats else None
		account = t.pop("gmail_account")
		t["can_open_gmail"] = int(bool(own_account) and account == own_account)
	return threads


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
				"creation": e.creation,
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
