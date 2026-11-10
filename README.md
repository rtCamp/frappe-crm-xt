# Frappe CRM XT

Extensions for [Frappe CRM](https://github.com/frappe/crm) that add features without forking the core app.

- **[Extensible sidebar](#extensible-sidebar-crm_sidebar-hook)** — any installed Frappe app can inject list views, routes, groups, or separators into the CRM sidebar via the `crm_sidebar` hook.
- **[Events tab](#events-tab)** — calendar events tab injected into every Lead and Deal page; create, edit, duplicate, and delete Frappe `Event` records linked to the record.
- **[Event notifications](#event-notifications)** — scheduler sends in-browser realtime alerts and optional emails to event owners and participants before their events.
- **[Deal inactivity follow-ups & Slack digest](#deal-inactivity-follow-ups--slack-digest)** — daily scheduler flags every CRM Deal with no activity (email, note, task, comment, or field edit) for *N* **working days** (holidays in the resolved Holiday List don't count), posts a single Slack digest, and optionally creates a plain follow-up CRM Task. Configured from the **CRM XT Settings** doctype (notification, working-day threshold, holiday list / the ERPNext CRM Settings company's holiday list, follow-up toggle + Jinja task title/body).
- **[Gmail Thread Reminder (incoming-email SLA)](#gmail-thread-reminder-incoming-email-sla)** — stamps a holiday-aware **due datetime** (`custom_incoming_sla_due`) on each deal = incoming-email time + a configurable number of **calendar hours** (default 24), maintained by the Gmail-thread sync. A **native Frappe Notification** (event *"Minutes After"* on that field) then posts a Slack channel alert — Frappe's own offset scheduler fires and dedups it, so this app writes no scheduler. Shares the deal-inactivity Holiday List and the `utils/holiday` helper.
- **Gmail thread activities** — activity entries on Lead/Deal records resolve Gmail threads via [`rtcamp/frappe_gmail_thread`](https://github.com/rtCamp/frappe_gmail_thread) *(optional)*.
- **[Address management (Deal only)](#address-management)** — add, create, link, and unlink `Address` records directly from Deal forms via an inline HTML panel.
- **[Follow button (eye icon)](#follow-button)** — injected into the Lead/Deal header icon row. Toggles `Document Follow` for the current user; filled eye = following, outline eye = not following.
- **Quotation auto-items** — opening a `Quotation` from a CRM Deal's "Create Quotation" link auto-populates items, customer, currency, and missing values from the source Deal.
- **Public Lead intake API** — guest-allowed `POST` endpoints for creating CRM Leads and uploading files against them; intended for website / external form integrations.
- **Gmail Add-on backend** — whitelisted endpoints powering the Gmail sidebar Add-on (contact lookup by email, linked Leads / Deals, latest activity).
- **Bundled fixtures** — Lead & Deal field layouts, Property Setters, Custom Fields, CRM Form Scripts, and a curated set of CRM View Settings ship as fixtures and install automatically. (Optional)
- **[Project creation on Won](#project-creation-on-won-deal)** — when a Deal is marked Won, dialogs guide the user through updating MSA & Insurance details on the linked Customer and creating an ERPNext `Project` pre-filled from the deal.

---

## Architecture

Frappe CRM XT ships a **Vite-built Vue 3 IIFE bundle** (`crm_xt_app.js`) that is loaded into the Frappe CRM SPA alongside the standard Frappe assets. The bundle:

- mounts a minimal `App.vue` root component on a `#crm-xt-app` div injected into the page
- uses `MutationObserver` to watch the CRM SPA's DOM and inject the sidebar, custom routes, and the Events tab without touching any FCRM source files
- ships its own copy of Vue 3 and [frappe-ui](https://github.com/frappe/frappe-ui), so all components use the same design tokens and Tailwind classes as native CRM views

### Frontend components

| Component | Purpose |
|-----------|---------|
| `App.vue` | Root — sidebar injection, route registration, Events tab injection |
| `ExtListView.vue` | Full-featured list view (frappe-ui `ListView`, filters, sort, column picker, pagination) |
| `InjectedEventsTab.vue` | Events tab timeline and empty state |
| `InjectedEventModal.vue` | Create / edit / delete / duplicate Event dialog |
| `EventNotifications.vue` | Per-event notification rules editor |
| `ListFilterLocal.vue` | Ad-hoc filter panel used inside `ExtListView` |
| `Attendee.vue` | Email-tag input for event attendees |
| `UserAvatar.vue` | Resolved user avatar with fallback initials |

### Backend modules

| Module | Purpose |
|--------|---------|
| `api/activity.py` | Overrides `crm.api.activities.get_activities`; appends Gmail thread entries |
| `api/event.py` | `get_doc_events`, create/save/delete helpers, notification scheduler tasks |
| `api/follow.py` | Document Follow toggle endpoint |
| `api/contact.py` | Gmail Add-on contact lookup endpoints |
| `api/quotation.py` | Quotation auto-populate helper |
| `api/search.py` | Overrides `search_link` so Link dropdowns show 20 rows |
| `api/sidebar.py` | Reads `crm_sidebar` hooks from all installed apps and returns merged item list |
| `tasks/deal_inactivity.py` | Daily "deal gone quiet" scheduler — creates follow-up tasks + posts the Slack digest, holiday-aware |
| `doc_events/incoming_sla.py` | Maintains `custom_incoming_sla_due` (incoming-email SLA) so a native "Minutes After" Notification can alert the owner |
| `utils/holiday.py` | Shared working-day / holiday helpers (used by the digest and the SLA-due field) |

---

## Features

### Events Tab

Every Lead and Deal page gains an **Events** tab injected at the right end of the tab bar.

**Capabilities:**

- Timeline feed of all `Event` records linked to the current Lead/Deal via `Event Participants`
- **Create** a new event — title, date/time or all-day, color, attendees (email tags), visibility, location, description
- **Edit** an existing event — all fields editable; changes saved via `frappe.client.save`
- **Delete** an event (with confirmation)
- **Duplicate** an event
- Color-coded accent bar per event card; color picker shows the active selection
- Participant avatar stack on each card (up to 3 + overflow count)

Events are stored as standard Frappe `Event` documents and also appear in the Frappe Desk Calendar (`/app/event`).

**Permissions note:** Events are fetched via `frappe_crm_xt.api.event.get_doc_events`, which bypasses the child-doctype read permission issue that prevents direct `frappe.client.get_list` calls on `Event Participants`.

---

### Event Notifications

Scheduler tasks fire at every interval and send notifications to event owners and participants ahead of their events.

Per-event rules can be configured in the `Event Notifications` child table on each Event record. If no per-event rules exist, global defaults from **FCRM Settings** are applied.

| Setting | Description |
|---------|-------------|
| `event_notifications` | Rules for timed events |
| `all_day_event_notifications` | Rules for all-day events |

Each rule specifies: `type` (Notification / Email), `before` (number), `interval` (minutes / hours / days / weeks), and optionally `time` (for all-day events).

---

### Deal Inactivity Follow-ups & Slack Digest

A daily scheduler (`cron` 14:00 / 2 PM, site time zone) processes every CRM Deal that has had **no activity for the configured number of WORKING days (default 7)** and flags it once per idle streak. For each such deal it:

1. **adds the deal to a single Slack digest**, and
2. (when *Create follow-up task* is on) **creates a plain follow-up CRM Task** on the deal (`Todo`, configured priority, assigned to the deal owner — no dates, no calendar sync).

Won/Lost deals are skipped.

**Working-days against one calendar:** the threshold counts only **working days** — days that are *not* in the resolved Holiday List. A single list applies to every deal (see below), so its holidays and weekly-offs don't add to the total: a deal idle Fri→Tue across a listed Sat/Sun (and any other listed holiday) has only accrued the working days in between. A deal is never nudged *on* a non-working day; it surfaces on the next working day. Non-working days come **only** from the resolved Holiday List (which normally includes its weekly-offs) — **if no Holiday List is resolved, every day counts (plain calendar days)**.

**Dedup is by the follow-up task's title:** a CRM Task with the (rendered) title, created since the deal's last activity, marks the streak as handled — so keep *Create follow-up task* enabled for once-per-streak behaviour on the digest. No hidden marker fields are used.

**Exact candidate window (no buffer):** each run considers only deals whose last activity falls in the *exact* calendar band that crosses `threshold` working days **today** — computed from the working-day sequence, so listed holidays stretch the band precisely (its lower bound is the `threshold+1`-th working day counting back). Per deal we then require the count to be **exactly** `threshold`, so consecutive working-day runs *tile* with no gap or overlap: a deal is flagged once, on its crossing working day, and never re-visited — no duplication and no dedup flag needed. The one gap: if the cron does **not run on a given working day** (scheduler downtime), that day's crossings are skipped (there is no buffer to re-scan them next day).

**Query cost:** per run it's one bounded candidate query, one grouped-`MAX` per activity source, and — for the working-day count — **one `Holiday` query** for the single resolved list (dates prefetched into an in-memory set; membership checks are then pure Python) plus at most **one `Company` lookup** for the ERPNext CRM Settings company. No per-day or per-deal holiday round-trips.

**Configuration lives on the `CRM XT Settings` single doctype** (editable by **System Manager** and **Sales Manager**). A future in-app *CRM XT* settings tab can read/write it; today it is editable from its desk form. Blank fields fall back to the defaults shown:

| Field | Role | Default |
|-------|------|---------|
| Notification | Link → **Notification** whose subject/message/Slack webhook drive the digest; its own `enabled` flag is the master on/off switch. **Blank ⇒ feature off.** | — |
| Inactivity Threshold (Working Days) | Working days of silence before a deal is nudged (holidays in the resolved Holiday List don't count). | `7` |
| Use the ERPNext CRM Settings company's holiday list | When on, **all** deals are evaluated against the `default_holiday_list` of the company set in **ERPNext CRM Settings** ("Company in ERPNext site"); falls back to the Holiday List below if that company has none. The list is **not** computed per deal. | off |
| Holiday List | Fixed calendar of non-working days for the skip/catch-up. No list resolved at all ⇒ every day counts (plain calendar days). | — |
| Create a follow-up task | Enables per-deal follow-up CRM Task creation. Digest still sends when off. | off |
| Task Priority | Priority of the follow-up task (`Low` / `Medium` / `High`). | `High` |
| Task Title | **Jinja** template rendered per deal (`{{ doc }}` = the CRM Deal). | `Follow up on inactive deal` |
| Task Body | **Jinja** template for the task description. | — |

Excluded statuses (Won/Lost) and internal constants (Slack size ceiling, comment-divider syntax) stay in code.

"Activity" is the most recent of **all** of the following — a note/task/comment does *not* bump `deal.modified`, so each is checked directly:

| Source | Field / record |
|--------|----------------|
| Status / any deal field edit | `deal.modified` |
| Incoming email | `deal.custom_last_incoming_email_time` |
| Outgoing email / reply | `deal.last_responded_on` (Gmail-synced) and/or `deal.custom_last_responded_on` (migrated) |
| Notes | `FCRM Note` |
| Tasks | `CRM Task` |
| Comments | `Comment` |

The digest itself is authored from the **Notification** selected in CRM XT Settings (the app seeds `CRM Slack — CRM Deal Inactivity (7 days)`, disabled) — no code change is needed to restyle or re-scope it:

| Notification field | Role in the digest |
|--------------------|--------------------|
| `enabled` | Master on/off switch for the whole routine — digest **and** tasks (the scheduler no-ops when disabled or when no Notification is selected) |
| `subject` | Digest **header** — rendered with `{{ count }}` and `{{ days }}` |
| `message` | Per-deal **block** — rendered with `{{ doc }}` (the deal) |
| Condition / Filters | Extra per-deal scoping, honored before creating a task or sending |
| Slack Webhook URL | Target Slack channel. Optional — with no webhook the follow-up tasks are still created; only the Slack post is skipped. |

**Dividers via Markdown comments:** any `<!-- ... -->` comment in the message is stripped from the Slack output (like a Markdown comment); the inner text of the first comment becomes the **divider between deal blocks** (`\n` is interpreted as a newline). No comment → blocks are separated by a blank line.

**Scales to large datasets:** instead of scanning every stale deal, the job fetches only deals whose last activity falls in the *exact* holiday-aware band that crosses `threshold` working days today (lower bound = the `threshold+1`-th working day back), so cost stays flat even with 100k+ deals.

The Notification is seeded (disabled) by the `create_crm_slack_notifications` patch, alongside two event-driven CRM → Slack notifications:

| Notification | Trigger |
|--------------|---------|
| CRM Slack — CRM Deal Inactivity (7 days) | Daily scheduler (this feature) |
| CRM Slack — CRM Deal Note Added | New `FCRM Note` on a Deal |
| CRM Slack — CRM Deal Updates | Deal saved (title / status / value / owner / stage change) |

All three ship **disabled**. Point each at a `Slack Webhook URL` (core Frappe integration) and toggle **Enabled** from the desk to activate — the webhook holds a secret, so it is never shipped in the app.

---

### Gmail Thread Reminder (incoming-email SLA)

Nudges the **deal owner** on Slack when an **incoming email** on the Gmail thread has gone **unanswered for N hours** (default 24, holiday-aware). This app does **no scheduling or sending** for it — it stamps a due datetime on the deal and lets Frappe's native Notification engine trigger.

**How it works:**

1. **Due field** — `custom_incoming_sla_due` (hidden) = `custom_last_incoming_email_time` advanced by the configured number of **calendar hours**, then — if that lands on a holiday in the resolved list — deferred to the next working day (`utils/holiday.add_hours_deferred`), so the alert never fires on a holiday (a Fri incoming + 24h landing on a listed Sat falls on Mon, never Sat). It reuses the digest's Holiday List.
2. **Maintained by the Gmail-thread sync** — `doc_events/incoming_sla.refresh_incoming_due`, called from `doc_events/gmail_thread.on_update` (the single writer of the incoming/response timestamps; some writes `db_set` past doc-event hooks, so a plain CRM Deal hook would miss them). The field is **cleared** when a reply lands after the incoming email, the deal closes (Won/Lost), or tracking is turned off.
3. **Trigger & dedup are Frappe's** — configure a **Notification** on **CRM Deal** with event **"Minutes After"**, datetime field **`custom_incoming_sla_due`**, minutes offset **≥ 10** (use `10`), channel **Slack** + a Slack Webhook URL. Frappe's offset scheduler (every 5 min) fires it once when `now` crosses `due + offset` and dedups via the Notification's own `datetime_last_run`. A newer incoming email recomputes the due datetime, so the alert **re-arms** on its own. Reference the owner in the message with plain `{{ doc.deal_owner }}` if you want it named.

**Config (CRM XT Settings → "Gmail Thread Reminder"):**

| Field | Role | Default |
|-------|------|---------|
| Track unanswered incoming email | Maintain the `custom_incoming_sla_due` field. Off ⇒ stop stamping it (pending ones clear on the next email sync). | off |
| Unanswered After (Hours) | Calendar hours after the incoming email before it falls due. If the due lands on a listed holiday the alert **defers to the next working day**, so it never fires on a holiday. | `24` |

The Notification's own **Enabled** flag is the on/off for actually sending. Nothing is seeded — create the Notification yourself so the webhook secret is never shipped.

---

### Address Management

Every CRM Deal form gains a custom **Addresses** HTML panel (not shown on CRM Lead). It renders all `Address` records linked to the Deal via `Dynamic Link`.

**Capabilities:**

- **List** all linked addresses with collapsible full-address detail
- **Create** a new address and automatically link it to the record
- **Link** an existing `Address` record by searching and selecting it
- **Unlink** an address (removes the Dynamic Link entry; does not delete the Address document)
- **Edit** — each card has a direct link to the address's Frappe Desk form

---

### Follow Button

An eye icon is injected into the Lead/Deal header icon row:

- **Filled eye** — you are currently following this record
- **Outline eye** — you are not following this record

Clicking the button calls the `frappe_crm_xt.api.follow.toggle_follow` endpoint and auto-enables `track_changes` on the doctype if needed.

---

### Project Creation on Won Deal

When a CRM Deal's status is set to **Won**, two sequential dialogs are shown automatically:

1. **MSA & Insurance Details** — pre-filled from the linked ERPNext `Customer`; saves MSA start/end date, document link, insurance requested flag, insurance start/end date, and insurance document link back to the Customer.
2. **Create Project** — collects Project Manager, Territory, Billing Type, Customer, Currency, Estimated Hours, Service Type, Opportunity Amount, and Project Type; creates an ERPNext `Project` and opens it in a new tab.

If a project matching the deal already exists, the creation dialog is skipped and an **Open Project** action is added to the Deal's action menu instead.

**Customer custom fields required** (shipped as fixtures in `custom_field.json`):

| Field | Type | Description |
|-------|------|-------------|
| `custom_msa_start_date` | Date | MSA start date |
| `custom_msa_end_date` | Date | MSA end date |
| `custom_msa_document_link` | Data | Link or path to MSA document |
| `custom_insurance_requested` | Check | Whether insurance was requested |
| `custom_insurance_start_date` | Date | Insurance start date |
| `custom_insurance_end_date` | Date | Insurance end date |
| `custom_insurance_document_link` | Data | Link or path to insurance document |

---

### Extensible Sidebar (`crm_sidebar` hook)

Any installed Frappe app can add items to the CRM sidebar by defining a `crm_sidebar` list in its `hooks.py`. Items appear below the built-in "Call Logs" entry.

Four item types are supported:

| `type` | Description |
|--------|-------------|
| `"list_view"` | Opens the built-in list view at `/xt/list/<doctype>` |
| `"route"` | Navigates to an arbitrary URL (internal or external) |
| `"separator"` | Renders a horizontal divider line |
| `"group"` | Collapsible section; child items live in the `"items"` key (one level deep) |

#### Full Hook Reference

```python
# hooks.py  (in any installed Frappe app)

crm_sidebar = [
    {
        # ── Required ──────────────────────────────────────────────────
        "label": "Purchase Orders",         # Sidebar display label
        "type": "list_view",                # "list_view" | "route" | "separator" | "group"

        # ── Required for type == "list_view" ──────────────────────────
        "doctype": "Purchase Order",

        # ── Required for type == "route" ──────────────────────────────
        # "url": "/app/purchase-order",

        # ── Optional ──────────────────────────────────────────────────
        "icon": "shopping-cart",            # Lucide icon name (lucide.dev/icons)

        # Filters shown in the filter UI — users can see and remove them
        "default_filters": {
            "status": ["=", "To Receive and Bill"],
        },

        # Filters always applied but never shown in the filter UI
        "hidden_filters": {
            "company": ["=", "My Company"],
        },

        # Columns to display (overrides DocType's in_list_view fields)
        "fields": ["supplier", "transaction_date", "status", "grand_total"],

        # Initial sort
        "default_sort": {"field": "transaction_date", "dir": "desc"},

        # Fieldname for the toolbar quick-search input
        # Type-aware: Link → autocomplete, Select/Check → dropdown,
        #             Date/Datetime → date picker, everything else → text
        "search_field": "supplier",

        # URL template opened on row click; {name} is replaced with the record name
        # Defaults to /app/<doctype-slug>/<name>
        "row_url": "/desk/query-report/{name}",
    },
    {"type": "separator"},
    {
        "label": "Procurement",
        "type": "group",
        "items": [
            {
                "label": "Suppliers",
                "type": "list_view",
                "doctype": "Supplier",
                "icon": "building",
            },
            {
                "label": "Support Portal",
                "type": "route",
                "url": "https://support.example.com",
                "icon": "external-link",
            },
        ],
    },
]
```

#### Option Reference

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `label` | `str` | ✅ | Sidebar display text |
| `type` | `str` | ✅ | `"list_view"`, `"route"`, `"separator"`, or `"group"` |
| `doctype` | `str` | `list_view` only | Frappe DocType to display |
| `url` | `str` | `route` only | Destination URL |
| `icon` | `str` | — | [Lucide](https://lucide.dev/icons/) icon name (default: `"list"`). Not supported on `group` — FCRM section headers are chevron + text only |
| `default_filters` | `dict` | — | Pre-applied filters; users can see and clear them |
| `hidden_filters` | `dict` | — | Always-applied filters; never shown in the UI |
| `fields` | `list[str]` | — | Column order override; title and Modified are always included |
| `default_sort` | `dict` | — | `{"field": "<fieldname>", "dir": "asc"\|"desc"}` |
| `search_field` | `str` | — | Fieldname for the toolbar quick-search input |
| `row_url` | `str` | — | Row-click URL template; `{name}` is replaced with the record name |
| `items` | `list` | `group` only | Child items (same schema, one level deep) |

---

### List View (`/xt/list/<doctype>`)

The built-in list view rendered for every `"list_view"` sidebar item includes:

- **Column picker** — toggle any field from the DocType on or off; selection persisted per-doctype in `localStorage`
- **Filter panel** — add, edit, and remove ad-hoc filters across any filterable field
- **Hidden filters** — `hidden_filters` from the hook are silently merged into every query; they do not appear in the filter panel
- **Type-aware quick search** — toolbar input whose component matches the `search_field` type:
  - `Link` → autocomplete (loads options from the linked DocType)
  - `Select` / `Check` → dropdown
  - `Date` / `Datetime` → date picker
  - Everything else → text input (`like %value%`)
- **Sort** — click any column header to toggle ascending/descending sort
- **Load More** — incremental pagination (20 rows per page)
- **Custom row URL** — `row_url` template determines row-click destination; defaults to the standard Frappe form view
- **Permission-safe** — if the user lacks read permission for the doctype, the list shows an empty state instead of crashing

---

## Requirements

| Package | Required |
|---------|----------|
| `crm` (Frappe CRM) | ✅ |
| `rtcamp/frappe_gmail_thread` | Optional — enables Gmail thread activity entries on Lead/Deal |
| `erpnext` | Optional — required for Project creation on Won Deal and Customer MSA/Insurance fields |

## Installation

```bash
bench get-app frappe_crm_xt
bench --site <your-site> install-app frappe_crm_xt
bench build --app frappe_crm_xt
bench --site <your-site> restart
```

## Development

```bash
# Install pre-commit hooks (runs ruff, oxlint, prettier, eslint on commit)
pre-commit install

# Frontend watch build (Vite IIFE bundle)
cd frontend && yarn dev

# Production build
cd frontend && yarn build

# Run linter
cd frontend && yarn lint
```

The Vite build outputs `frappe_crm_xt/public/js/crm_xt_app.js` (IIFE, ~1.5 MB) and `frappe_crm_xt/public/js/frappe-crm-xt-frontend.css`. Run `bench build --app frappe_crm_xt` afterwards to have Frappe copy the assets to the site's `public/` directory.

## Architecture Notes

- The Events tab and sidebar items are injected into the Frappe CRM SPA via a `MutationObserver` in `App.vue` — no FCRM source files are modified.
- The injected Events tab button deliberately does **not** carry `role="tab"` to avoid Reka UI intercepting the click and collapsing all panels.
- `get_doc_events` uses `ignore_permissions=True` only on the `Event Participants` child-table queries (which have no standalone doctype-level permission); parent `Event` records respect normal read permissions.
- The `crm_sidebar` hook is collected from all installed apps via `frappe.get_hooks('crm_sidebar')` in `api/sidebar.py` and returned as a single merged list to the frontend.
- `frappe_crm_xt` must be listed **after** `crm` in `apps.txt` so the `override_whitelisted_methods` entry for `crm.api.activities.get_activities` takes precedence correctly.

## License

[GNU Affero General Public License v3.0](license.txt)
