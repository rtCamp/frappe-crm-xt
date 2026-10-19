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


@frappe.whitelist()
def search_candidate_threads(doctype: str, docname: str):
	"""Search for Gmail threads linked to a given doctype/docname or any of its emails."""
	if doctype not in ["CRM Lead", "CRM Deal"]:
		return []

	frappe.has_permission(doctype, "read", doc=docname, throw=True)
	emails = _collect_emails(doctype, docname)
	if not emails:
		return []

	like_clauses = []
	params: list = []
	for e in emails:
		like_clauses += ["e.sender = %s", "e.recipients LIKE %s", "e.cc LIKE %s"]
		params += [e, f"%{e}%", f"%{e}%"]

	user = frappe.session.user
	rows = frappe.db.sql(
		f"""
		SELECT
			t.name,
			t.subject_of_first_mail,
			t.gmail_thread_id,
			t.reference_doctype,
			t.reference_name,
			MAX(e.creation) AS last_email_on,
			COUNT(e.name) AS num_emails,
			(ga.linked_user = %s) AS can_open_gmail
		FROM `tabGmail Thread` t
		JOIN `tabSingle Email CT` e ON e.parent = t.name
		LEFT JOIN `tabGmail Account` ga ON ga.name = t.gmail_account
		WHERE ({" OR ".join(like_clauses)})
		  AND (t.reference_name IS NULL OR t.reference_name = ''
		       OR (t.reference_doctype = %s AND t.reference_name = %s))
		GROUP BY t.name
		ORDER BY last_email_on DESC
		LIMIT 50
		""",
		(user, *params, doctype, docname),
		as_dict=True,
	)
	return [r for r in rows if frappe.has_permission("Gmail Thread", "read", doc=r["name"])]


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
