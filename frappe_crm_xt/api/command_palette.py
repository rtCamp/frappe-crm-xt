"""Override of `crm.api.command_palette.search`: deals match and show by Title.

Leads need nothing: CRM sets a lead's title to its organization or lead name, both already searched.
"""

from __future__ import annotations

import frappe
from crm.api.command_palette import (
	SEARCH_TYPES,
	_get_recent,
	_get_upcoming,
	_parse_recent,
	_search_activity,
	_search_doctype,
)

# A local copy, not an edit of CRM's: its module is shared by every site on the worker.
CRM_XT_SEARCH_TYPES = {
	**SEARCH_TYPES,
	"CRM Deal": ("Deal", "title", ["title", "organization", "email", "mobile_no"]),
}


@frappe.whitelist()
def search(query: str = "", recent_names: str | None = None):
	"""Return permission-filtered CRM records for the command palette."""
	query = (query or "").strip()
	recent = _parse_recent(recent_names)
	result = {
		"matches": _search_all(query) if len(query) >= 2 else [],
		"activity": _search_activity(query) if len(query) >= 2 else [],
		"recent": _get_recent(recent) if not query else [],
		"upcoming": _get_upcoming() if not query else [],
	}
	_retitle_deals(result)
	return result


def _search_all(query: str):
	results = []
	for doctype, config in CRM_XT_SEARCH_TYPES.items():
		if frappe.has_permission(doctype, "read"):
			results.extend(_search_doctype(doctype, config, query))
	return results


def _retitle_deals(result: dict):
	"""Use the deal Title in the sections CRM titles from its own SEARCH_TYPES (by organization)."""
	# (row, key that holds the title, deal name); CRM already limited these rows to readable deals
	rows = [(r, "title", r["name"]) for r in result["recent"] if r["doctype"] == "CRM Deal"]
	rows += [
		(r, "parent_title", r["parent_name"]) for r in result["activity"] if r["parent_doctype"] == "CRM Deal"
	]
	rows += [
		(r, "title", r["name"]) for r in result["upcoming"] if r["kind"] == "sla" and r["route"] == "Deal"
	]
	if not rows:
		return
	names = list({name for _r, _k, name in rows})
	titles = dict(frappe.get_all("CRM Deal", {"name": ["in", names]}, ["name", "title"], as_list=True))
	for row, key, name in rows:
		row[key] = titles.get(name) or row[key]
