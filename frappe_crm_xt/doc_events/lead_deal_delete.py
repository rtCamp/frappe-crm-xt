"""on_trash for CRM Lead and CRM Deal."""

from __future__ import annotations

import frappe
from frappe.query_builder import Case
from frappe.query_builder.functions import Count, Sum

_LINK_PARENT_DOCTYPES = ("Contact", "Address")
_GMAIL_THREAD = "Gmail Thread"

_DELETE_WHEN_ORPHANED = ("Address",)


def on_trash(doc, method=None):
	for parent_dt in _LINK_PARENT_DOCTYPES:
		link_filters = {
			"parenttype": parent_dt,
			"link_doctype": doc.doctype,
			"link_name": doc.name,
		}

		if parent_dt in _DELETE_WHEN_ORPHANED:
			_detach_or_delete(parent_dt, link_filters)
		else:
			# Just drop the back-reference rows; the parent record stays.
			frappe.db.delete("Dynamic Link", link_filters)

	for thread_name in frappe.get_all(
		_GMAIL_THREAD,
		filters={"reference_doctype": doc.doctype, "reference_name": doc.name},
		pluck="name",
	):
		# db.set_value bypasses Gmail Thread's own validate hook (which would
		# re-read the now-empty reference fields and reject the update).
		frappe.db.set_value(
			_GMAIL_THREAD,
			thread_name,
			{"reference_doctype": "", "reference_name": ""},
			update_modified=False,
		)


def _detach_or_delete(parent_dt, link_filters):
	"""For each parent linked to the doc being trashed: if our link is its only
	one, delete the parent outright (delete_doc cascades its child rows); else
	just remove our back-reference row, leaving the parent intact."""
	dl = frappe.qb.DocType("Dynamic Link")
	ours = Sum(
		Case()
		.when(
			(dl.link_doctype == link_filters["link_doctype"]) & (dl.link_name == link_filters["link_name"]),
			1,
		)
		.else_(0)
	)
	rows = (
		frappe.qb.from_(dl)
		.select(dl.parent, Count(dl.name).as_("total"), ours.as_("ours"))
		.where(dl.parenttype == link_filters["parenttype"])
		.groupby(dl.parent)
		.having(ours > 0)
		.run(as_dict=True)
	)

	for row in rows:
		name = row.parent
		if row.total > row.ours:
			frappe.db.delete("Dynamic Link", {**link_filters, "parent": name})
			continue

		try:
			frappe.delete_doc(parent_dt, name, delete_permanently=True)
		except Exception:
			frappe.db.delete("Dynamic Link", {**link_filters, "parent": name})
			frappe.log_error(
				title="Address already Linked [Delete Failed]",
				message=f"{parent_dt} {name}: {frappe.get_traceback()}",
			)
