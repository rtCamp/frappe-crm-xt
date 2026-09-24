from __future__ import annotations

import re
from itertools import zip_longest

import frappe

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


# CRM Task was never indexed for global search, so searching it always came
# back empty — left off rather than offered as a dead filter.
LEAD_DOCTYPE = "CRM Lead"
SEARCH_FILTER_DOCTYPES = {
	"CRM Lead": LEAD_DOCTYPE,
	"CRM Deal": "CRM Deal",
	"CRM Organization": "CRM Organization",
	"FCRM Note": "FCRM Note",
	"Contact": "Contact",
}

# frappe_search always prefixes an excerpt with a "Name: <docname>" field of
# its own — the row's title already shows the record, so that's just noise.
# And the "Converted : 0/1" field, when indexed, is redundant with the
# Converted badge a Lead result gets below. Both get stripped before display.
LEADING_NAME_FIELD_RE = re.compile(r"^Name\s*:\s*[\s\S]*?(?:<br>\s*|$)", re.IGNORECASE)
CONVERTED_FIELD_RE = re.compile(r"\s*(?:<br>\s*)?Converted\s*:\s*[01]\b\s*(?:<br>)?", re.IGNORECASE)


def _clean_excerpt(text: str) -> str:
	text = LEADING_NAME_FIELD_RE.sub("", text)
	text = CONVERTED_FIELD_RE.sub(" ", text)
	return text.strip()


def _allowed_search_filters() -> list[str]:
	"""SEARCH_FILTER_DOCTYPES narrowed to what Global Search Settings actually
	has indexed (Global Search DocType) and the current user can read, so a
	filter only shows up when its underlying doctype is genuinely searchable."""
	from frappe.desk.doctype.global_search_settings.global_search_settings import (
		get_doctypes_for_global_search,
	)

	indexed = set(get_doctypes_for_global_search())
	readable = set(frappe.get_user().get_can_read())
	return [f for f, dt in SEARCH_FILTER_DOCTYPES.items() if dt in indexed and dt in readable]


@frappe.whitelist()
def get_search_filters():
	"""Filter keys the frontend may offer, plus whether more than one can be
	picked at once. frappe_search can search several doctypes in a single
	call; the core frappe.utils.global_search fallback only ever takes one
	doctype at a time, so the frontend renders a single-select there."""
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
			frappe.throw(f"Unknown search filter(s): {', '.join(unknown)}")
		active_filters = doctypes
	else:
		active_filters = allowed_filters

	real_doctypes = list({SEARCH_FILTER_DOCTYPES[f] for f in active_filters})

	# One search per doctype, not a single call spanning all of them: both
	# frappe_search and the core fallback rank-then-LIMIT across every
	# doctype in one query, so a doctype with few matches (e.g. CRM Deal)
	# can get crowded out of the result window entirely by one with many
	# (e.g. CRM Lead), even though both genuinely match. Querying each
	# doctype on its own budget guarantees every selected doctype gets a
	# fair shot.
	# ponytail: `start` is reused as-is for every doctype's query rather than
	# tracking an independent cursor per doctype, so "Load More" can revisit
	# or skip a few rows within a doctype once several are mixed together —
	# fine for a search dropdown, revisit if that's ever actually noticeable.
	use_frappe_search = "frappe_search" in frappe.get_installed_apps()
	if use_frappe_search:
		from frappe_search.api.search import get_global_search_results
	else:
		from frappe.utils.global_search import search as global_search

	by_doctype = {}
	for dt in real_doctypes:
		if use_frappe_search:
			raw = get_global_search_results(
				text=text, start=start, limit=limit + 1, doctype=dt, allowed_doctypes=[dt]
			)
			rows = raw[0] if (isinstance(raw, list | tuple) and len(raw) == 2) else raw
		else:
			raw = global_search(text, start=start, limit=limit + 1, doctype=dt) or []
			rows = [
				{
					"doctype": r.get("doctype"),
					"name": r.get("name"),
					"title": r.get("title") or r.get("name"),
					"marked_string": r.get("content") or r.get("name"),
					"score": r.get("rank", 0),
				}
				for r in raw
			]
		by_doctype[dt] = sorted(rows, key=lambda r: r.get("score", 0), reverse=True)

	# Round-robin across doctypes instead of pooling everything and sorting by
	# score: fuzzy-match scores land on a handful of common values, so a
	# global sort-then-truncate lets ties get decided by fetch order — one
	# doctype could win every tied slot and push an equally-relevant match
	# from another doctype off the page entirely.
	results = [r for group in zip_longest(*by_doctype.values()) for r in group if r is not None]

	# The converted flag isn't part of the search index, so it's looked up
	# separately here — used to badge each Lead row as Converted/Active.
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
		# `marked_string` is a context-cropped snippet around the match — good for
		# a one-line preview, but it cuts fields off mid-value. `full_marked_string`
		# (frappe_search only) is the same field dump, uncropped, so the frontend
		# can show every indexed field in full instead of a truncated fragment.
		r["marked_string"] = _clean_excerpt(
			r.get("full_marked_string") or r.get("marked_string") or r.get("name") or ""
		)

	has_more = len(results) > limit
	return results[:limit], has_more
