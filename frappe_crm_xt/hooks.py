app_name = "frappe_crm_xt"
app_title = "Frappe CRM XT"
app_publisher = "rtcamp"
app_description = "FCRM extensions: frappe_search bar and extensible sidebar list views."
app_email = "support@rtcamp.com"
app_license = "agpl-3"

required_apps = ["crm"]

fixtures = [
	{"dt": "CRM Form Script", "filters": [["is_standard", "=", 0]]},
]


doc_events = {
	"CRM Lead": {
		"on_trash": "frappe_crm_xt.doc_events.lead_deal_delete.on_trash",
	},
	"CRM Deal": {
		"validate": "frappe_crm_xt.doc_events.deal.validate",
		"before_save": "frappe_crm_xt.doc_events.deal.before_save",
		"after_insert": "frappe_crm_xt.doc_events.deal.after_insert",
		# After FCRM's on_update, which creates the ERPNext Customer on Won.
		"on_update": "frappe_crm_xt.doc_events.deal.on_update",
		"on_trash": "frappe_crm_xt.doc_events.lead_deal_delete.on_trash",
	},
	"CRM Organization": {
		"on_update": "frappe_crm_xt.doc_events.organization.sync_deals",
	},
	"Address": {
		"validate": "frappe_crm_xt.doc_events.organization.on_address_validate",
	},
	"CRM Task": {
		"validate": "frappe_crm_xt.doc_events.task.validate",
		"on_trash": [
			"frappe_crm_xt.doc_events.task.on_trash",
			"frappe_crm_xt.doc_events.calendar_sync.delete_event_on_task_trash",
		],
		"on_update": "frappe_crm_xt.doc_events.calendar_sync.sync_task_to_calendar",
	},
	"Gmail Thread": {
		"validate": "frappe_crm_xt.doc_events.gmail_thread.validate",
		"on_update": "frappe_crm_xt.doc_events.gmail_thread.on_update",
	},
	"Project": {
		"after_insert": "frappe_crm_xt.doc_events.project.after_insert",
	},
	"FCRM Note": {
		"validate": "frappe_crm_xt.doc_events.fcrm_note.validate",
	},
}


override_whitelisted_methods = {
	# Append frappe_gmail_thread activity entries to FCRM's activity feed.
	"crm.api.activities.get_activities": "frappe_crm_xt.api.activity.get_activities",
	# Temp fix until frappe/crm#2187 is merged: SQL-level CRM-role filter
	# replaces 173k-iteration per-user loop in crm.api.session.get_users.
	"crm.api.session.get_users": "frappe_crm_xt.api.session.get_users",
	# Hide Contact/Address/Gmail Thread from the linked-docs modal when the
	# parent is a Lead/Deal — upstream can't actually unlink them, so showing
	# them as blockers is misleading. They get cleaned up via on_trash above.
	"crm.api.doc.get_linked_docs_of_document": "frappe_crm_xt.api.doc.get_linked_docs_of_document",
	# Bump Link dropdown default page_length 10 → 20 (frontend sends none).
	"frappe.desk.search.search_link": "frappe_crm_xt.api.search.search_link",
}


doctype_js = {
	"Quotation": "public/js/quotation_auto_items.js",
}


global_search_doctypes = {
	"Default": [
		{"doctype": "CRM Lead"},
		{"doctype": "CRM Deal"},
		{"doctype": "FCRM Note"},
	]
}


scheduler_events = {
	"all": ["frappe_crm_xt.api.event.trigger_offset_event_notifications"],
	"hourly": ["frappe_crm_xt.api.event.trigger_hourly_event_notifications"],
	"daily": ["frappe_crm_xt.api.event.trigger_daily_event_notifications"],
	"weekly": ["frappe_crm_xt.api.event.trigger_weekly_event_notifications"],
	"cron": {
		"0 14 * * *": ["frappe_crm_xt.tasks.deal_inactivity.notify_inactive_deals"],
	},
}

# ─── CRM Sidebar hook ─────────────────────────────────────────────────────────
#
# Any installed Frappe app can define this hook to inject items into the FCRM
# sidebar (inserted below "Call Logs").
#
# Each item is a dict with the following keys:
#
#   label          (str, required)
#       Sidebar display label, e.g. "Purchase Orders"
#
#   type           (str, required)  "list_view" | "route" | "separator" | "group"
#       "list_view"  - opens /xt/list/<doctype> with the built-in list view.
#       "route"      - navigates to an arbitrary URL (internal or external).
#       "separator"  - renders a horizontal divider line; no other keys needed.
#       "group"      - collapsible section; child items live in the "items" key.
#
#   doctype        (str)  Required when type == "list_view".
#       Frappe DocType name, e.g. "Purchase Order"
#
#   url            (str)  Required when type == "route".
#       Destination URL, e.g. "/app/purchase-order" or "https://example.com"
#
#   icon           (str, optional)  Lucide icon name (default: "list")
#       Not supported on type == "group": FCRM section headers are chevron +
#       text only (frappe-ui SidebarLabel has no icon slot), so a group icon
#       would be the one header in the sidebar that looks different.
#       Any of the 1600+ Lucide icon names work — see https://lucide.dev/icons/
#       Common examples: users, user, briefcase, file-text, package,
#         shopping-cart, tag, inbox, phone, calendar, square-check,
#         dollar-sign, trending-up, activity, star, settings, grid-2x2,
#         building, building-2, list, external-link, link, layout-grid
#
#   default_filters (dict, optional)
#       Filters pre-applied when the list view opens AND shown in the filter UI.
#       Users can see and remove these filters.
#       Format: { "fieldname": ["operator", "value"], ... }
#       Example: { "status": ["=", "Open"], "priority": ["=", "High"] }
#
#   hidden_filters (dict, optional)
#       Filters always applied to every query but NEVER shown in the filter UI.
#       Users cannot see or remove these filters — useful for scoping a view to
#       a specific subset without cluttering the filter panel.
#       Format: { "fieldname": ["operator", "value"], ... }
#       Example: { "is_standard": ["=", "Yes"], "module": ["=", "CRM"] }
#
#   fields          (list[str], optional)
#       Ordered list of fieldnames to display as columns.
#       Overrides the auto-detected in_list_view columns from the DocType.
#       The title field and "Modified" are always included automatically.
#       Example: ["item_name", "status", "supplier", "grand_total"]
#
#   default_sort    (dict, optional)
#       Initial sort applied when the list opens.
#       Keys: "field" (fieldname str) and "dir" ("asc" | "desc").
#       Example: { "field": "creation", "dir": "desc" }
#
#   row_url         (str, optional)
#       URL template opened when a row is clicked.
#       Use {name} as a placeholder for the record name (URL-encoded automatically).
#       Defaults to /app/{doctype-slug}/{name}  (standard Frappe form view).
#       Example: "/desk/query-report/{name}"  →  opens the ERPNext report runner
#
#   items           (list, optional)  Only for type == "group".
#       Child items — each follows the same schema (list_view, route, separator).
#       Groups do NOT nest inside other groups (only one level deep).
#
#   search_field    (str, optional)
#       Fieldname used for the always-visible quick-search input in the toolbar.
#       Defaults to the doctype's title field (usually "name").
#       The input component is chosen automatically based on the field's type:
#         Data / Small Text / Text  → text input  (uses "like %value%" filter)
#         Select / Check            → dropdown    (uses "=" filter)
#         Link                      → autocomplete (uses "=" filter, loads options
#                                      from the linked doctype)
#         Date / Datetime           → date picker  (uses "=" filter)
#         Int / Float / Currency    → text input   (uses "=" filter)
#       Example: "supplier"  (shows supplier autocomplete in the toolbar)
#
# ─── Example ──────────────────────────────────────────────────────────────────
#
# crm_sidebar = [
#     {
#         "label": "Purchase Orders",
#         "type": "list_view",
#         "doctype": "Purchase Order",
#         "icon": "shopping-cart",   # any name from lucide.dev/icons
#         "default_filters": {"status": ["=", "To Receive and Bill"]},
#         "hidden_filters":  {"company": ["=", "My Company"]},   # always applied, not shown
#         "fields": ["supplier", "transaction_date", "status", "grand_total"],
#         "default_sort": {"field": "transaction_date", "dir": "desc"},
#     },
#     {"type": "separator"},          # ── horizontal divider ──────────────────
#     {
#         "label": "Procurement",     # ── collapsible group ───────────────────
#         "type": "group",
#         "items": [
#             {
#                 "label": "Suppliers",
#                 "type": "list_view",
#                 "doctype": "Supplier",
#                 "icon": "building",
#             },
#             {"type": "separator"},
#             {
#                 "label": "Support Portal",
#                 "type": "route",
#                 "url": "https://support.example.com",
#                 "icon": "external-link",
#             },
#         ],
#     },
# ]
#
crm_sidebar = [
	{"type": "separator"},
	{
		"label": "List Views",
		"type": "group",
		"items": [
			{
				"label": "Reports",
				"type": "list_view",
				"doctype": "Report",
				"icon": "chart-bar",
				"fields": ["name", "ref_doctype", "is_standard", "report_type"],
				"default_sort": {"field": "modified", "dir": "desc"},
				"row_url": "/desk/query-report/{name}",
			},
			{
				"label": "Converted Leads",
				"type": "list_view",
				"doctype": "CRM Lead",
				"icon": "users",
				"fields": ["name", "title", "organization", "status", "creation"],
				"default_filters": {"converted": ["=", "1"]},
				"row_url": "/crm/leads/{name}",
			},
		],
	},
]

# ─── Setup hooks ──────────────────────────────────────────────────────────────
#
# Install/refresh the CRM-side custom fields that mirror rtcamp's ERPNext-side
# customisations. Lets the ERPNext → Frappe CRM migrator auto-map fields by
# same-name match without any per-row review by the user.
#
# create_custom_fields(..., update=True) is idempotent — safe to call on every
# migrate.

after_install = "frappe_crm_xt.setup.after_install"
after_migrate = "frappe_crm_xt.setup.install"
