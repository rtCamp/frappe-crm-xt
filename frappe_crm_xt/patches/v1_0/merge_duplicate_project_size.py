"""Merge the duplicate "Project Size" field on CRM Deal into `custom_project_size` (rtCamp/erp-rtcamp#2929).

CRM Deal had two identical Select fields, `custom_project_size` and `custom__project_size`. We keep
`custom_project_size`; the code now uses it (layout, deal.py mapping to Project, CRM form script).

1. Copy `custom__project_size` into `custom_project_size` on deals where `custom_project_size` is
   empty.
2. Deals where both are filled with different values go on a skip list: they aren't touched, and
   the list is written to the Error Log.
3. Point CRM Deal's field layouts and list views (CRM Fields Layout, CRM View Settings) at
   `custom_project_size`.
4. Only if the skip list is empty: delete the `custom__project_size` Custom Field and drop its
   column.

If deals were skipped, resolve them by hand, then run the patch again:
    bench --site <site> run-patch frappe_crm_xt.patches.v1_0.merge_duplicate_project_size --force
"""

import json
import re
from typing import Any

import click
import frappe

DOCTYPE = "CRM Deal"
KEEP = "custom_project_size"
STALE = "custom__project_size"
SET_VALUE_CHUNK = 500

# Keys under which CRM layouts and list views store a fieldname inside list items.
REFERENCE_KEYS = ("key", "fieldname")
VIEW_JSON_FIELDS = ("columns", "rows", "filters", "kanban_columns", "kanban_fields")
VIEW_SCALAR_FIELDS = ("group_by_field", "column_field", "title_field")


def execute() -> None:
	if not frappe.db.table_exists(DOCTYPE) or not frappe.db.has_column(DOCTYPE, STALE):
		return

	moved, skipped = move_values()
	layouts = update_layouts()
	views = update_view_settings()
	click.secho(
		f"Project Size: copied {moved} deal(s) into {KEEP}, skipped {len(skipped)}, "
		f"updated {layouts} layout(s) and {views} list view(s).",
		fg="green",
	)

	if skipped:
		frappe.log_error(
			title=f"Project Size merge: {len(skipped)} deal(s) skipped",
			message=(
				f"Both {KEEP} and {STALE} are filled with different values on these deals, so they "
				f"were not changed and {STALE} was not removed. Resolve them, then re-run "
				f"the patch with --force.\n\n{json.dumps(skipped, indent=1)}"
			),
		)
		click.secho(
			f"{len(skipped)} deal(s) have different values in both fields; {STALE} kept. See Error Log.",
			fg="yellow",
		)
		return

	if remove_stale_field():
		click.secho(f"Removed {STALE} (Custom Field and column).", fg="green")


def _is_blank(value: Any) -> bool:
	return value is None or not str(value).strip()


def _deals_with_stale_value() -> list[dict[str, Any]]:
	"""Return name and both values for every deal that has something in the stale field."""
	deal = frappe.qb.DocType(DOCTYPE)
	return (
		frappe.qb.from_(deal)
		.select(deal.name, deal[KEEP].as_("keep"), deal[STALE].as_("stale"))
		.where(deal[STALE].isnotnull() & (deal[STALE] != ""))
		.run(as_dict=True)
	)


def move_values() -> tuple[int, list[dict[str, Any]]]:
	"""Copy the stale value where the kept field is empty. Returns (deals copied, skip list)."""
	to_move: dict[str, list[str]] = {}
	skipped: list[dict[str, Any]] = []
	for row in _deals_with_stale_value():
		if _is_blank(row.stale):
			continue
		if _is_blank(row.keep):
			to_move.setdefault(row.stale, []).append(row.name)
		elif row.keep != row.stale:
			skipped.append({"deal": row.name, KEEP: row.keep, STALE: row.stale})

	# One set_value per distinct value (at most 3 Select options), chunked, not one per deal.
	for value, names in to_move.items():
		for start in range(0, len(names), SET_VALUE_CHUNK):
			frappe.db.set_value(
				DOCTYPE,
				{"name": ("in", names[start : start + SET_VALUE_CHUNK])},
				KEEP,
				value,
				update_modified=False,
			)
	return sum(len(names) for names in to_move.values()), skipped


def _refers_to(item: Any, fieldname: str) -> bool:
	if isinstance(item, str):
		return item == fieldname
	if isinstance(item, dict):
		return any(item.get(key) == fieldname for key in REFERENCE_KEYS)
	return False


def swap_field(value: Any) -> Any:
	"""Point every reference to the stale field at the kept one.

	Where the kept field is already listed next to it (same list or dict), the stale entry is
	dropped instead of renamed, so views don't end up with the field twice.
	"""
	if isinstance(value, dict):
		out: dict[str, Any] = {}
		for key, item in value.items():
			if key == STALE:
				if KEEP in value:
					continue
				key = KEEP
			out[key] = KEEP if (key in REFERENCE_KEYS and item == STALE) else swap_field(item)
		return out
	if isinstance(value, list):
		out_list: list[Any] = []
		has_keep = any(_refers_to(item, KEEP) for item in value)
		for item in value:
			if _refers_to(item, STALE):
				if has_keep:
					continue
				has_keep = True
			out_list.append(KEEP if item == STALE else swap_field(item))
		return out_list
	return value


def _swap_json(raw: str | None) -> str | None:
	"""Return the JSON text with references swapped, or None if nothing changed or it isn't JSON."""
	if not raw or STALE not in raw:
		return None
	try:
		parsed = json.loads(raw)
	except ValueError:
		return None
	swapped = swap_field(parsed)
	return json.dumps(swapped) if swapped != parsed else None


def update_layouts() -> int:
	"""Update CRM Deal's CRM Fields Layout records. Other doctypes (e.g. Opportunity) are untouched."""
	updated = 0
	for layout in frappe.get_all("CRM Fields Layout", filters={"dt": DOCTYPE}, fields=["name", "layout"]):
		new_layout = _swap_json(layout.layout)
		if new_layout is not None:
			frappe.db.set_value("CRM Fields Layout", layout.name, "layout", new_layout, update_modified=False)
			updated += 1
	return updated


def update_view_settings() -> int:
	"""Update CRM Deal's list/kanban/group-by views that show, filter or sort by the stale field."""
	meta = frappe.get_meta("CRM View Settings")
	json_fields = [f for f in VIEW_JSON_FIELDS if meta.has_field(f)]
	scalar_fields = [f for f in VIEW_SCALAR_FIELDS if meta.has_field(f)]
	order_field = "order_by" if meta.has_field("order_by") else None
	fields = ["name", *json_fields, *scalar_fields, *([order_field] if order_field else [])]
	stale_word = re.compile(rf"\b{re.escape(STALE)}\b")

	updated = 0
	for view in frappe.get_all("CRM View Settings", filters={"dt": DOCTYPE}, fields=fields):
		changes: dict[str, str] = {}
		for field in json_fields:
			new_value = _swap_json(view.get(field))
			if new_value is not None:
				changes[field] = new_value
		for field in scalar_fields:
			if view.get(field) == STALE:
				changes[field] = KEEP
		if order_field and stale_word.search(view.get(order_field) or ""):
			changes[order_field] = stale_word.sub(KEEP, view.get(order_field))
		if changes:
			frappe.db.set_value("CRM View Settings", view.name, changes, update_modified=False)
			updated += 1
	return updated


def remove_stale_field() -> bool:
	"""Delete the stale Custom Field and drop its column, after re-checking that no value would be lost."""
	at_risk = [
		row.name for row in _deals_with_stale_value() if not _is_blank(row.stale) and row.keep != row.stale
	]
	if at_risk:
		frappe.log_error(
			title="Project Size merge: field not removed",
			message=f"{STALE} still holds values not in {KEEP} on: {at_risk}",
		)
		return False

	custom_field = frappe.db.get_value("Custom Field", {"dt": DOCTYPE, "fieldname": STALE})
	if custom_field:
		# delete_doc runs CustomField.on_trash (removes its Property Setters and layout rows) and
		# keeps a Deleted Document copy. ignore_permissions: runs as a migrate patch, no user session.
		frappe.delete_doc("Custom Field", custom_field, ignore_permissions=True)

	if frappe.db.has_column(DOCTYPE, STALE):
		# Raw DDL: frappe.qb has no ALTER TABLE, and deleting a Custom Field never drops its column.
		# Both names are module constants, not user input.
		frappe.db.sql_ddl(f"ALTER TABLE `tab{DOCTYPE}` DROP COLUMN `{STALE}`")
		frappe.cache.delete_value(f"table_columns::tab{DOCTYPE}")

	frappe.clear_cache(doctype=DOCTYPE)
	return True
