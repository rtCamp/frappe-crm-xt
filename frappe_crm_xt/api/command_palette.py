"""Override of `crm.api.command_palette.search`: deals match and show by Title.

Leads need nothing: CRM sets a lead's title to its organization or lead name, both already searched.
"""

from __future__ import annotations

import frappe
from crm.api import command_palette

# (route, title_field, search_fields) — same shape as CRM's SEARCH_TYPES
TITLE_SEARCH_TYPES = {
	"CRM Deal": ("Deal", "title", ["title", "organization", "email", "mobile_no"]),
}


@frappe.whitelist()
def search(query: str = "", recent_names: str | None = None):
	# CRM's helpers all read SEARCH_TYPES; our entries are constant, so updating it is idempotent.
	command_palette.SEARCH_TYPES.update(TITLE_SEARCH_TYPES)
	return command_palette.search(query=query, recent_names=recent_names)
