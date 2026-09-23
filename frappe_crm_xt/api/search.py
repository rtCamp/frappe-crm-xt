from __future__ import annotations

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
CRM_SEARCH_DOCTYPES = ["CRM Lead", "CRM Deal", "CRM Organization", "FCRM Note", "Contact"]


def _allowed_search_doctypes() -> list[str]:
	"""CRM_SEARCH_DOCTYPES narrowed to what Global Search Settings actually has
	indexed (Global Search DocType) and the current user can read, so a doctype
	only shows up as a search filter when it's genuinely searchable."""
	from frappe.desk.doctype.global_search_settings.global_search_settings import (
		get_doctypes_for_global_search,
	)

	indexed = set(get_doctypes_for_global_search())
	readable = set(frappe.get_user().get_can_read())
	return [dt for dt in CRM_SEARCH_DOCTYPES if dt in indexed and dt in readable]


@frappe.whitelist()
def get_search_filters():
	"""Doctypes the frontend may offer as filters, plus whether more than one
	can be picked at once. frappe_search can search several doctypes in a
	single call; the core frappe.utils.global_search fallback only ever takes
	one doctype at a time, so the frontend renders a single-select there."""
	return {
		"doctypes": _allowed_search_doctypes(),
		"multi": "frappe_search" in frappe.get_installed_apps(),
	}


@frappe.whitelist()
def get_search_results(text: str, start: int = 0, limit: int = 10, doctypes: list[str] | None = None):
	start = int(start)
	limit = int(limit)
	allowed_doctypes = _allowed_search_doctypes()

	if doctypes:
		unknown = [d for d in doctypes if d not in allowed_doctypes]
		if unknown:
			frappe.throw(f"Unknown search filter(s): {', '.join(unknown)}")
		allowed_doctypes = doctypes

	if "frappe_search" in frappe.get_installed_apps():
		from frappe_search.api.search import get_global_search_results

		raw = get_global_search_results(
			text=text,
			start=start,
			limit=limit,
			allowed_doctypes=allowed_doctypes,
		)
		results_list, has_more = (
			(raw[0], raw[1]) if (isinstance(raw, list | tuple) and len(raw) == 2) else (raw, False)
		)
		if len(results_list) > limit:
			has_more = True
			results_list = list(results_list)[:limit]
		return results_list, has_more

	from frappe.utils.global_search import search as global_search

	# Core global_search only accepts a single doctype. The frontend never
	# leaves the fallback UI with more than one filter selected, but fall back
	# to unrestricted rather than guessing if that ever happens.
	doctype = allowed_doctypes[0] if len(allowed_doctypes) == 1 else ""
	raw = global_search(text, start=start, limit=limit + 1, doctype=doctype) or []

	has_more = len(raw) > limit
	results = []
	for r in raw[:limit]:
		results.append(
			{
				"doctype": r.get("doctype"),
				"name": r.get("name"),
				"title": r.get("title") or r.get("name"),
				"marked_string": r.get("content") or r.get("name"),
			}
		)

	return results, has_more
