# Frappe CRM XT

Extensions for [Frappe CRM](https://github.com/frappe/crm). The app adds features to CRM without a fork of the core app. It uses hooks, API overrides, CRM Form Scripts and a small Vue bundle that loads into the CRM single-page app.

Supported version: Frappe CRM v16 (Frappe Framework v16).

## Features

| Area | Feature |
|------|---------|
| Navigation | [Extensible sidebar](#extensible-sidebar-crm_sidebar-hook) and [list view](#list-view-xtlistdoctype) for any DocType |
| Search | [Deal title in the command palette](#search) and 20 rows in Link dropdowns |
| Calendar | [Events tab](#events-tab) on leads and deals, [event notifications](#event-notifications), [task calendar sync](#task-calendar-sync) |
| Deals | [Stage change log and checklists](#stage-change-log-and-checklists), [organization sync](#organization-sync), [address panel](#address-panel), [follow button](#follow-button), probability validation |
| Follow-ups | [Deal inactivity digest](#deal-inactivity-digest) and [incoming email reminder](#incoming-email-reminder) |
| Email | [Gmail thread integration](#gmail-thread-integration) *(optional)* |
| Delete | [Clean delete of leads and deals](#clean-delete-of-leads-and-deals) |
| ERPNext | [Quotation auto-items](#quotation-auto-items) *(optional)* |
| Notes | [Note posting date](#note-posting-date) |

## Requirements

| App | Required |
|-----|----------|
| `crm` (Frappe CRM v16) | Yes |
| `erpnext` | Optional. Needed for Quotation auto-items and holiday lists from a company. |
| `frappe_gmail_thread` | Optional. Needed for the Gmail thread integration. |

## Installation

```bash
bench get-app frappe_crm_xt
bench --site <your-site> install-app frappe_crm_xt
bench build --app frappe_crm_xt
bench --site <your-site> migrate
```

Install `frappe_crm_xt` after `crm`. The API overrides in this app replace CRM methods, so `crm` must load first.

On install and on each migrate, the app applies its custom fields and property setters. On install only, it also seeds the default Lead and Deal field layouts.

---

## Navigation

### Extensible sidebar (`crm_sidebar` hook)

Any installed app can add items to the CRM sidebar. Define a `crm_sidebar` list in the `hooks.py` of that app. The items show below the built-in CRM items.

| `type` | Result |
|--------|--------|
| `"list_view"` | Opens the built-in [list view](#list-view-xtlistdoctype) at `/xt/list/<doctype>` |
| `"route"` | Opens an internal or external URL |
| `"separator"` | Shows a horizontal line |
| `"group"` | Shows a collapsible section. Put the child items in `"items"` (one level only). |

```python
# hooks.py (in any installed app)
crm_sidebar = [
    {
        "label": "Purchase Orders",
        "type": "list_view",
        "doctype": "Purchase Order",
        "icon": "shopping-cart",
        "default_filters": {"status": ["=", "To Receive and Bill"]},
        "hidden_filters": {"company": ["=", "My Company"]},
        "fields": ["supplier", "transaction_date", "status", "grand_total"],
        "default_sort": {"field": "transaction_date", "dir": "desc"},
        "search_field": "supplier",
        "row_url": "/app/purchase-order/{name}",
    },
    {"type": "separator"},
    {
        "label": "Procurement",
        "type": "group",
        "items": [
            {"label": "Suppliers", "type": "list_view", "doctype": "Supplier", "icon": "building"},
            {"label": "Support", "type": "route", "url": "https://support.example.com", "icon": "external-link"},
        ],
    },
]
```

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `label` | `str` | Yes | Text in the sidebar |
| `type` | `str` | Yes | `"list_view"`, `"route"`, `"separator"` or `"group"` |
| `doctype` | `str` | `list_view` | DocType to list |
| `url` | `str` | `route` | Destination URL |
| `icon` | `str` | No | [Lucide](https://lucide.dev/icons/) icon name. The default is `"list"`. Groups do not show icons. |
| `default_filters` | `dict` | No | Filters that the user can see and remove |
| `hidden_filters` | `dict` | No | Filters that always apply and do not show in the UI |
| `fields` | `list[str]` | No | Columns to show. The title and Modified columns are always included. |
| `default_sort` | `dict` | No | `{"field": "<fieldname>", "dir": "asc" \| "desc"}` |
| `search_field` | `str` | No | Field for the quick search input in the toolbar |
| `row_url` | `str` | No | URL to open on row click. `{name}` becomes the record name. The default is the Desk form. |
| `items` | `list` | `group` | Child items with the same keys |

This app uses the hook itself to add a **List Views** group with **Reports** and **Converted Leads**.

### List view (`/xt/list/<doctype>`)

Each `"list_view"` sidebar item opens a list view with these functions:

- **Column picker.** Show or hide any field. The browser keeps the selection for each DocType.
- **Filters.** Add, change and remove filters on any filterable field. Hidden filters from the hook always apply.
- **Quick search.** The input type follows the `search_field` type: autocomplete for Link, a dropdown for Select and Check, a date picker for Date and Datetime, and text for all other types.
- **Sort.** Click a column header to sort.
- **Load more.** The list loads 20 rows at a time.
- **Permissions.** If the user cannot read the DocType, the list shows an empty state.

---

## Search

- **Command palette.** CRM's ⌘K search finds deals by organization, email and mobile number only, and shows the organization as the result title. This app adds the deal **Title** field to the search and shows it as the result title. Leads need no change, because CRM sets the lead title from the organization or the lead name.
- **Link dropdowns.** Frappe returns 10 rows by default. This app changes the default to 20, which is the maximum that the CRM dropdown shows.

---

## Calendar

### Events tab

Each lead and deal page gets an **Events** tab at the end of the tab bar. The tab lists the Frappe `Event` records that link to the record through `Event Participants`.

- Create, edit, copy and delete events.
- Set the title, color, date and time or all day, attendees, visibility, location, description and notifications.
- Each event card shows a color bar and up to three participant avatars.

Events are standard `Event` documents, so they also show in the Desk calendar.

### Event notifications

Scheduled jobs send a realtime alert, an email or both to the event owner and participants before an event starts.

Set the rules for one event in its **Event Notifications** table. If an event has no rules, the defaults from **FCRM Settings** apply:

| Setting | Use |
|---------|-----|
| `event_notifications` | Rules for timed events |
| `all_day_event_notifications` | Rules for all-day events |

Each rule has a type (Notification or Email), a number, an interval (minutes, hours, days or weeks) and, for all-day events, a time.

### Task calendar sync

A CRM Task has a **Sync with Calendar** option. When it is on, the app creates and updates an `Event` for the task. When it is off, or when the task is deleted, the app deletes the event. The task must have the fields that the event needs, and the due date must be after the start time.

---

## Deals

### Stage change log and checklists

- **Stage change log.** Each change of the deal stage adds a row with the old stage, the new stage, the dates, the duration and the user.
- **Checklists.** Add checklist items to a **CRM Deal Status** or a **Sales Stage**. When a deal enters that status or stage, the app creates a CRM Task that contains the checklist. The app does not create a second task while an open task with the same title exists.

### Organization sync

When an organization changes, the app copies the changed details to all deals of that organization. Deals created through Data Import or the API also get the organization details. The open list views update in real time.

### Address panel

Each deal form has an **Addresses** panel. It lists the `Address` records that link to the deal.

- Create an address and link it to the deal.
- Link an existing address.
- Unlink an address. The address record stays.
- Open an address in Desk.

### Follow button

An eye icon in the lead and deal header follows or unfollows the record for the current user. A filled eye means that you follow the record. The app turns on **Track Changes** for the DocType if it is off.

### Probability validation

A form script and a server check keep the deal probability between 0 and 100.

---

## Follow-ups

Both features use the **CRM XT Settings** single DocType. System Managers and Sales Managers can edit it.

### Deal inactivity digest

A daily job (14:00, site time zone) finds deals with no activity for a set number of **working days**. For each run it:

1. Sends one Slack digest that lists the inactive deals.
2. Optionally creates a follow-up CRM Task for each deal, assigned to the deal owner.

Won and Lost deals are skipped. The job flags a deal once for each period of inactivity.

**Activity** is the latest of these:

| Source | Field or record |
|--------|-----------------|
| Any deal field change | `modified` |
| Incoming email | `custom_last_incoming_email_time` |
| Reply | `last_responded_on` or `custom_last_responded_on` |
| Note, task, comment | `FCRM Note`, `CRM Task`, `Comment` |

**Working days.** Days in the resolved Holiday List do not count. If no list is resolved, all days count. A deal is never flagged on a holiday. It is flagged on the next working day.

| Setting | Use | Default |
|---------|-----|---------|
| Notification | The Notification that sends the digest. Blank turns the feature off. | — |
| Inactivity Threshold (Working Days) | Working days with no activity | `7` |
| Use the ERPNext CRM Settings company's holiday list | Use the default holiday list of the company in **ERPNext CRM Settings** | Off |
| Holiday List | The holiday list to use when the company option is off or the company has no list | — |
| Create a follow-up task | Create a CRM Task for each flagged deal | Off |
| Task Priority | Priority of the task | `High` |
| Task Title | Jinja template. `{{ doc }}` is the deal. | `Follow up on inactive deal` |
| Task Body | Jinja template for the task description | — |

The selected Notification controls the digest:

| Notification field | Use |
|--------------------|-----|
| Enabled | Turns the digest and the tasks on or off |
| Subject | Digest header. Use `{{ count }}` and `{{ days }}`. |
| Message | Block for each deal. Use `{{ doc }}`. |
| Condition | Limits the deals |
| Slack Webhook URL | Target channel. Without a webhook, the app still creates the tasks. |

Text in the first `<!-- ... -->` comment of the message becomes the divider between deal blocks. Use `\n` for a new line.

The job reads only the deals whose last activity falls on the exact day range that reaches the threshold today. This keeps the job fast on large data sets.

A patch adds three Slack notifications. All are disabled. Set a Slack Webhook URL and enable them in Desk:

| Notification | Trigger |
|--------------|---------|
| CRM Slack — CRM Deal Inactivity (7 days) | The daily job |
| CRM Slack — CRM Deal Note Added | A new note on a deal |
| CRM Slack — CRM Deal Updates | A change to the deal title, status, value, owner or stage |

### Incoming email reminder

This feature sends a Slack alert when an incoming email on a deal has no reply after a set number of hours. The app does not schedule anything. It sets a due time on the deal, and a standard Frappe Notification sends the alert.

1. The Gmail thread sync sets `custom_incoming_sla_due` to the incoming email time plus the set hours. If the due time falls on a holiday, it moves to the next working day.
2. The app clears the due time when a reply arrives, when the deal is Won or Lost, or when the feature is off.
3. Create a Notification on **CRM Deal** with the event **Minutes After**, the date field `custom_incoming_sla_due`, an offset of at least 10 minutes and the **Slack** channel. Frappe sends it once. A new incoming email sets a new due time.

| Setting | Use | Default |
|---------|-----|---------|
| Track unanswered incoming email | Turns the due time on or off | Off |
| Unanswered After (Hours) | Hours after the incoming email | `24` |

---

## Gmail thread integration

These functions need the `frappe_gmail_thread` app.

- **Activity feed.** Gmail threads show in the lead and deal activity feed.
- **Thread linker.** A form action on leads and deals finds threads by the record's email addresses or by subject, shows a preview and links the thread.
- **Lead conversion.** When a lead converts to a deal, its threads move to the deal.
- **Response times.** The sync records the last incoming email, the first and last reply and the users who took part in the thread.
- **Gmail Add-on backend.** Whitelisted methods return the contact, leads, deals and latest activity for an email address. They check read permission before they return data.

---

## Clean delete of leads and deals

- **Linked documents.** The delete dialog does not list Contact, Address and Gmail Thread, because CRM cannot unlink them. The app removes these links when the record is deleted.
- **Addresses.** If the deleted record was the only link of an address, the app deletes the address.

---

## Quotation auto-items

When a user creates a Quotation from a deal, the app fills the items, customer, currency and other missing values from the deal.

## Note posting date

Notes get a **Posting Date** that defaults to now. The date cannot be in the future. The note's creation time matches the posting date.

---

## Architecture

The app has two parts:

- **Backend.** Doc events, scheduled jobs, `override_whitelisted_methods`, custom fields, property setters and CRM Form Script fixtures.
- **Frontend bundle.** Vite builds a Vue 3 IIFE bundle (`crm_xt_app.js`) that loads into the CRM single-page app. A `MutationObserver` in `App.vue` adds the sidebar items, the `/xt/` routes, the Events tab and the follow button. The app does not change CRM source files.

The bundle has its own copy of [frappe-ui](https://github.com/frappe/frappe-ui). CRM v16 uses a newer frappe-ui that changed class names, for example `rounded` became `rounded-4`. `frontend/src/styles/bundle.css` maps the old class names that the bundle uses to the new CRM design tokens. These rules are global on purpose: CRM elements that still use the old names also get their corners back.

### API overrides

| CRM or Frappe method | Change |
|----------------------|--------|
| `crm.api.activities.get_activities` | Adds Gmail thread entries |
| `crm.api.command_palette.search` | Searches and shows deals by Title |
| `crm.api.doc.get_linked_docs_of_document` | Hides Contact, Address and Gmail Thread for leads and deals |
| `crm.api.session.get_users` | Filters CRM users in SQL, not in a loop over all users |
| `frappe.desk.search.search_link` | Returns 20 rows by default |

### Frontend components

| Component | Use |
|-----------|-----|
| `App.vue` | Root. Adds the sidebar items, routes, Events tab and follow button. |
| `ExtListView.vue`, `ExtListRows.vue` | List view for sidebar items |
| `ListFilterLocal.vue` | Filter panel of the list view |
| `InjectedEventsTab.vue` | Events tab |
| `InjectedEventModal.vue` | Event create and edit dialog |
| `EventNotifications.vue` | Notification rules of an event |
| `Attendee.vue`, `UserAvatar.vue` | Attendee input and avatars |

---

## Development

```bash
pre-commit install            # ruff, oxlint, prettier, eslint
cd frontend && yarn dev       # watch build
cd frontend && yarn build     # production build
cd frontend && yarn lint
```

The build writes `frappe_crm_xt/public/js/crm_xt_app.js` and `frappe_crm_xt/public/js/frappe-crm-xt-frontend.css`. These files are not in git. Run `bench build --app frappe_crm_xt` to copy them to the site assets.

If the build runs out of memory, set `NODE_OPTIONS=--max-old-space-size=3400`.

Run the tests:

```bash
bench --site <your-site> run-tests --app frappe_crm_xt
```

## License

[GNU Affero General Public License v3.0](license.txt)
