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


# "Converted Lead" isn't a real doctype — CRM Lead has a `converted` checkbox,
# so it's modelled as a second filter over the same doctype, split by that flag.
SEARCH_FILTERS = {
	"CRM Lead": {"doctype": "CRM Lead", "converted": 0},
	"Converted Lead": {"doctype": "CRM Lead", "converted": 1},
	"CRM Deal": {"doctype": "CRM Deal"},
	"CRM Organization": {"doctype": "CRM Organization"},
	"FCRM Note": {"doctype": "FCRM Note"},
	"CRM Task": {"doctype": "CRM Task"},
	"Contact": {"doctype": "Contact"},
}


def _search_one_doctype(text, doctype, limit):
	"""Full-text search restricted to a single real doctype (permission-checked by the callee)."""
	if "frappe_search" in frappe.get_installed_apps():
		from frappe_search.api.search import get_global_search_results

		raw, _ = get_global_search_results(
			text=text, start=0, limit=limit, doctype=doctype, allowed_doctypes=[doctype]
		)
		return raw or []

	from frappe.utils.global_search import search as global_search

	return global_search(text, limit=limit, doctype=doctype) or []


@frappe.whitelist()
def get_search_results(text: str, start: int = 0, limit: int = 10, doctype: str | None = None):
	start = int(start)
	limit = int(limit)

	if doctype and doctype not in SEARCH_FILTERS:
		frappe.throw(f"Unknown search filter: {doctype}")

	active_filters = [doctype] if doctype else list(SEARCH_FILTERS.keys())
	real_doctypes = {SEARCH_FILTERS[f]["doctype"] for f in active_filters}

	# The converted flag isn't in the search index, so it's applied as a
	# post-filter below — overfetch CRM Lead to compensate for rows it drops.
	fetch_size = start + limit + 1
	lead_fetch_size = fetch_size * 2

	raw_by_doctype = {
		dt: _search_one_doctype(text, dt, lead_fetch_size if dt == "CRM Lead" else fetch_size)
		for dt in real_doctypes
	}

	converted_by_name = {}
	if "CRM Lead" in raw_by_doctype:
		lead_names = [r["name"] for r in raw_by_doctype["CRM Lead"]]
		converted_by_name = {
			d.name: d.converted
			for d in frappe.get_all(
				"CRM Lead", filters={"name": ["in", lead_names]}, fields=["name", "converted"]
			)
		}

	combined = []
	for f in active_filters:
		cfg = SEARCH_FILTERS[f]
		rows = raw_by_doctype[cfg["doctype"]]
		if "converted" in cfg:
			rows = [r for r in rows if converted_by_name.get(r["name"], 0) == cfg["converted"]]
		for r in rows:
			combined.append({**r, "filter": f})

	combined.sort(key=lambda r: r.get("rank", 0), reverse=True)
	page = combined[start : start + limit + 1]
	has_more = len(page) > limit

	results = []
	for r in page[:limit]:
		results.append(
			{
				"doctype": r.get("filter"),
				"name": r.get("name"),
				"title": r.get("title") or r.get("name"),
				"marked_string": r.get("content") or r.get("name"),
			}
		)

	return results, has_more
