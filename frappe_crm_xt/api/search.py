from __future__ import annotations

import frappe
from frappe import _

# Frappe's search_link defaults to 10 rows; the CRM Link control never sends a
# page_length, so dropdowns top out at 10. Bump the default to 20 — the most the
# frontend Autocomplete renders (maxOptions=20). Higher needs a frontend change.
LINK_PAGE_LENGTH = 20


@frappe.whitelist()
def search_link(
	doctype: str,
	txt: str,
	query: str | None = None,
	filters: str | dict | list | None = None,
	page_length: int | None = None,
	searchfield: str | None = None,
	reference_doctype: str | None = None,
	ignore_user_permissions: bool = False,
	*,
	link_fieldname: str | None = None,
):
	"""Default page_length to 20, then delegate to the live search_link override (rtcamp's, else core)."""
	page_length = page_length or LINK_PAGE_LENGTH

	# rtcamp also overrides search_link (custom_enabled/disabled filtering). Chain
	# through it so that behaviour is preserved; fall back to core when absent.
	if "rtcamp" in frappe.get_installed_apps():
		from rtcamp.override.search_link_override import search_link_override

		return search_link_override(
			doctype,
			txt,
			query=query,
			filters=filters,
			page_length=page_length,
			searchfield=searchfield,
			reference_doctype=reference_doctype,
			ignore_user_permissions=ignore_user_permissions,
		)

	from frappe.desk import search as _search

	return _search.search_link(
		doctype,
		txt,
		query=query,
		filters=filters,
		page_length=page_length,
		searchfield=searchfield,
		reference_doctype=reference_doctype,
		ignore_user_permissions=ignore_user_permissions,
		link_fieldname=link_fieldname,
	)


LEAD_DOCTYPE = "CRM Lead"
# CRM Task was never indexed for global search, so it always came back empty.
SEARCH_FILTER_DOCTYPES = [LEAD_DOCTYPE, "CRM Deal", "CRM Organization", "FCRM Note", "Contact"]


def _strip_mark(text: str) -> str:
	return text.replace("<mark>", "").replace("</mark>", "")


def _clean_excerpt(text: str) -> str:
	"""Drop the leading "Name: <docname>" field and any "Converted : 0/1"
	field (already shown as a badge) — labels are compared with <mark>
	stripped, since frappe_search highlights a match anywhere, including
	inside a field's own label, e.g. "<mark>Converted</mark> : 1"."""
	segments = [s.strip() for s in text.split("<br>")]
	kept = []
	for i, seg in enumerate(segments):
		label = _strip_mark(seg).split(":", 1)[0].strip().lower()
		if (i == 0 and label == "name") or label == "converted":
			continue
		kept.append(seg)
	return " <br> ".join(kept).strip()


def _allowed_search_filters() -> list[str]:
	"""SEARCH_FILTER_DOCTYPES narrowed to what's indexed in Global Search
	Settings and readable by the current user."""
	from frappe.desk.doctype.global_search_settings.global_search_settings import (
		get_doctypes_for_global_search,
	)

	indexed = set(get_doctypes_for_global_search())
	readable = set(frappe.get_user().get_can_read())
	return [dt for dt in SEARCH_FILTER_DOCTYPES if dt in indexed and dt in readable]


@frappe.whitelist()
def get_search_filters():
	"""Filter keys the frontend may offer, plus whether more than one can be
	picked at once (only frappe_search supports multi-doctype search)."""
	return {
		"filters": _allowed_search_filters(),
		"multi": "frappe_search" in frappe.get_installed_apps(),
	}


@frappe.whitelist()
def get_search_results(text: str, start: int = 0, limit: int = 20, doctypes: list[str] | None = None):
	start = int(start)
	limit = int(limit)
	allowed_filters = _allowed_search_filters()

	if doctypes:
		unknown = [f for f in doctypes if f not in allowed_filters]
		if unknown:
			frappe.throw(_("Unknown search filter(s): {0}").format(", ".join(unknown)))
		active_filters = doctypes
	else:
		active_filters = allowed_filters

	# active_filters doubles as the real doctype list — no indirection needed
	# now that every filter key is its own doctype's name.
	real_doctypes = active_filters

	if "frappe_search" in frappe.get_installed_apps():
		from frappe_search.api.search import get_global_search_results

		# frappe_search filters by fuzzy score, exists() and has_permission()
		# *after* its own SQL LIMIT, so an overfetch-by-one here wouldn't
		# reliably signal "more pages exist" — trust its own has_more instead.
		# It also stays the actual `limit` so successive pages' lookahead
		# queries land on the same (start, limit) cache key as the next
		# page's primary query, instead of always missing the cache by one.
		raw = get_global_search_results(text=text, start=start, limit=limit, allowed_doctypes=real_doctypes)
		results, has_more = (
			(raw[0], raw[1]) if (isinstance(raw, list | tuple) and len(raw) == 2) else (raw, False)
		)
	else:
		from frappe.utils.global_search import search as global_search

		# Core global_search only accepts a single doctype. The frontend never
		# leaves the fallback UI with more than one filter selected, but fall
		# back to unrestricted rather than guessing if that ever happens.
		doctype = real_doctypes[0] if len(real_doctypes) == 1 else ""
		raw = global_search(text, start=start, limit=limit + 1, doctype=doctype) or []
		has_more = len(raw) > limit
		raw = raw[:limit]
		results = [
			{
				"doctype": r.get("doctype"),
				"name": r.get("name"),
				"title": r.get("title") or r.get("name"),
				# Core content is "|||"-joined, not "<br>" — _clean_excerpt and
				# the frontend both split on "<br>", so without this a fallback
				# row renders as one field: label the first value, the rest
				# squashed into it.
				"marked_string": (r.get("content") or r.get("name") or "").replace("|||", "<br>"),
			}
			for r in raw
		]

	# The converted flag isn't part of the search index — badges each Lead row.
	lead_names = [r["name"] for r in results if r.get("doctype") == LEAD_DOCTYPE]
	converted_by_name = (
		{
			d.name: d.converted
			for d in frappe.get_all(
				LEAD_DOCTYPE, filters={"name": ["in", lead_names]}, fields=["name", "converted"]
			)
		}
		if lead_names
		else {}
	)

	for r in results:
		if r.get("doctype") == LEAD_DOCTYPE:
			r["converted"] = bool(converted_by_name.get(r["name"]))
		# full_marked_string (frappe_search only) is uncropped, unlike marked_string.
		r["marked_string"] = _clean_excerpt(
			r.get("full_marked_string") or r.get("marked_string") or r.get("name") or ""
		)

	return results, has_more
