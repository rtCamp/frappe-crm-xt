<template><div hidden /></template>

<script setup>
import { ref, onMounted, onUnmounted, h, createApp } from 'vue'
import ExtListView from './ExtListView.vue'
import InjectedEventsTab from './InjectedEventsTab.vue'
import {
  cloneNativeRow,
  cloneNativeSectionLabel,
  findNativeRow,
  createSectionLabel,
  findNativeSectionLabel,
  findSidebarEl,
  isModernSidebar,
  isSidebarCollapsed,
  setRowActive,
  lucideIconInner,
  setLabelCollapsed,
} from '../utils/sidebarRow.js'

const sidebarItems = ref([])

// ── Generic fetch helper ────────────────────────────────────────────────────
function csrf() {
  return window.csrf_token || window.boot?.csrf_token || ''
}

function apiGet(method) {
  return fetch(`/api/method/${method}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-Frappe-CSRF-Token': csrf(),
      Accept: 'application/json',
    },
    body: JSON.stringify({}),
  })
    .then((r) => r.json())
    .then((d) => d.message)
}

// ── Load sidebar items from Python hook ─────────────────────────────────────
async function loadSidebarItems() {
  try {
    const items = await apiGet('frappe_crm_xt.api.sidebar.get_sidebar_items')
    sidebarItems.value = Array.isArray(items) ? items : []
    injectFCRMRoute()
    injectCustomSidebarBtns()
  } catch (err) {
    // Sidebar is non-essential; if the API call fails the rest of the app
    // should keep working. Log so the failure is visible in devtools/Sentry
    // instead of silently disappearing.
    console.error('[crm-xt] Failed to load sidebar items:', err)
  }
}

// ── Recursively search sidebar items for a doctype config ───────────────────
function findItemForDoctype(items, doctype) {
  for (const item of items) {
    if (item.doctype === doctype) return item
    if (item.type === 'group' && Array.isArray(item.items)) {
      const found = findItemForDoctype(item.items, doctype)
      if (found) return found
    }
  }
  return null
}

const _extShim = {
  name: 'CrmXtListView',
  render() {
    return h('div', { class: 'flex-1 min-h-0 overflow-hidden' })
  },
  mounted() {
    this._mountApp(this.$route?.params?.doctype || '')
  },
  beforeUnmount() {
    this._app?.unmount()
    this._app = null
  },
  beforeRouteUpdate(to) {
    this._mountApp(to.params?.doctype || '')
  },
  methods: {
    _mountApp(doctype) {
      if (this._app) {
        this._app.unmount()
        this._app = null
      }
      if (!doctype) return
      // Look up hook config — search recursively inside groups too
      const itemCfg = findItemForDoctype(sidebarItems.value, doctype) || {}
      // eslint-disable-next-line vue/one-component-per-file -- createApp mount, not a component definition
      this._app = createApp(ExtListView, {
        doctype,
        defaultFilters: itemCfg.default_filters || {},
        hiddenFilters: itemCfg.hidden_filters || {},
        fields: itemCfg.fields || [],
        defaultSort: itemCfg.default_sort || {},
        searchField: itemCfg.search_field || '',
        rowUrl: itemCfg.row_url || '',
      })
      this._app.mount(this.$el)
    },
  },
}

// ── Inject our list-view route into FCRM's Vue Router ───────────────────────
// FCRM's router is configured with base="/crm", so all route paths are
// relative to that base (e.g. "/leads" not "/crm/leads").
let _routeAttempts = 0
function injectFCRMRoute() {
  if (_routeAttempts++ > 30) return
  const router =
    document.querySelector('#app')?.__vue_app__?.config?.globalProperties
      ?.$router
  if (!router) {
    setTimeout(injectFCRMRoute, 200)
    return
  }

  const routes = router.getRoutes()
  if (routes.some((r) => r.path === '/xt/list/:doctype')) return

  try {
    router.addRoute({ path: '/xt/list/:doctype', component: _extShim })
    // If the page loaded directly on one of our routes, the router already
    // resolved to a 404/redirect before we registered the route.  Re-push
    // the current location so the newly-added route can match.
    const loc = window.location.pathname // e.g. /crm/xt/list/CRM%20Lead
    const base = '/crm'
    const routerPath = loc.startsWith(base) ? loc.slice(base.length) : loc
    if (/^\/xt\/list\//i.test(routerPath)) {
      router.replace(routerPath + window.location.search + window.location.hash)
    }
  } catch (e) {
    console.warn('[crm-xt] route injection failed', e)
  }
}

const _findNativeRow = () => findNativeRow(document)
const _cloneNativeRow = cloneNativeRow

let _sidebarEl = null

function _findSidebarEl() {
  if (_sidebarEl && !_sidebarEl.isConnected) _sidebarEl = null
  if (_sidebarEl) return _sidebarEl
  _sidebarEl = findSidebarEl(document)
  return _sidebarEl
}

function _isSidebarCollapsed() {
  return isSidebarCollapsed(_findSidebarEl())
}

// Apply or remove collapsed styles to all our custom injected elements.
function _syncCollapse() {
  const collapsed = _isSidebarCollapsed()

  // Inner padding divs
  document.querySelectorAll('[data-xt-inner]').forEach((d) => {
    if (collapsed) {
      d.classList.remove('px-2', 'py-[7px]')
      d.classList.add('ml-[3px]', 'p-1')
    } else {
      d.classList.remove('ml-[3px]', 'p-1')
      d.classList.add('px-2', 'py-[7px]')
    }
  })

  document.querySelectorAll('[data-xt-label]').forEach((el) => {
    setLabelCollapsed(el, collapsed)
  })

  document.querySelectorAll('[data-xt-link]').forEach((el) => {
    el.classList.toggle('pl-2', !collapsed)
    el.classList.toggle('justify-center', collapsed)
  })
  document.querySelectorAll('[data-xt-icon]').forEach((el) => {
    el.classList.toggle('size-7', collapsed)
  })

  // Group chevrons and ⌘K badge — hide in collapsed mode
  document.querySelectorAll('[data-xt-hide-collapsed]').forEach((el) => {
    el.style.display = collapsed ? 'none' : ''
  })

  // Separators — hide in collapsed mode (no visual purpose for icon-only rail)
  document.querySelectorAll('[data-xt-sep]').forEach((el) => {
    el.style.display = collapsed ? 'none' : ''
  })

  document.querySelectorAll('[data-xt-divider]').forEach((el) => {
    el.style.display = collapsed ? 'flex' : 'none'
  })

  document.querySelectorAll('[data-xt-children]').forEach((el) => {
    if (collapsed) {
      el.style.display = 'flex'
      return
    }
    const header = el.parentElement?.querySelector('[aria-expanded]')
    el.style.display =
      header?.getAttribute('aria-expanded') === 'true' ? 'flex' : 'none'
  })
}

let _collapseObserver = null
let _collapseObserverTarget = null

function _setupCollapseObserver() {
  const sidebar = _findSidebarEl()
  if (!sidebar) return
  if (_collapseObserverTarget === sidebar) {
    _syncCollapse()
    return
  }
  _collapseObserver?.disconnect()
  _collapseObserver = new MutationObserver(_syncCollapse)
  _collapseObserver.observe(sidebar, {
    attributes: true,
    attributeFilter: ['class', 'style'],
  })
  _collapseObserverTarget = sidebar
  _syncCollapse()
}

function _teardownCollapseObserver() {
  _collapseObserver?.disconnect()
  _collapseObserver = null
  _collapseObserverTarget = null
}

// ── Build a sidebar nav button (shared by top-level and group children) ──────
function _sidebarItemHref(item) {
  if (item.type === 'list_view' && item.doctype)
    return `/crm/xt/list/${encodeURIComponent(item.doctype)}`
  return item.url || item.route || ''
}

function _sidebarItemAction(item) {
  return () => {
    if (item.type === 'list_view' && item.doctype) {
      const path = _sidebarItemHref(item)
      window.history.pushState({}, '', path)
      window.dispatchEvent(new PopStateEvent('popstate'))
      _syncActiveRow()
    } else {
      const url = item.url || item.route || ''
      if (url.startsWith('http')) window.open(url, '_blank')
      else window.location.href = url
    }
  }
}

function _makeSidebarBtn(item) {
  const isRoute = item.type === 'route'
  const icon = item.icon || (isRoute ? 'external-link' : 'list')
  const href = _sidebarItemHref(item)
  const row = _cloneNativeRow(_findNativeRow(), {
    label: item.label,
    icon,
    href: href.startsWith('http') ? undefined : href,
    onClick: _sidebarItemAction(item),
  })
  if (item.type === 'list_view' && href) row.setAttribute('data-xt-href', href)
  return row
}

// crm highlights the row whose route is current; our clones are inert DOM, so the
// same state has to be driven from the location.
function _syncActiveRow() {
  const here = decodeURIComponent(window.location.pathname)
  document.querySelectorAll('[data-xt-href]').forEach((row) => {
    const target = decodeURIComponent(row.getAttribute('data-xt-href'))
    setRowActive(row, target === here)
  })
}

// ── Inject custom sidebar buttons below "Call Logs" ──────────────────────────
function injectCustomSidebarBtns() {
  if (!sidebarItems.value.length) return

  const callLogsBtn = _findNativeRow()
  if (!callLogsBtn) return

  let anchor = callLogsBtn

  sidebarItems.value.forEach((item, idx) => {
    // ── Separator ────────────────────────────────────────────────────────────
    if (item.type === 'separator') {
      const id = `crm-xt-sb-sep-${idx}`
      if (document.getElementById(id)) {
        anchor = document.getElementById(id)
        return
      }
      const hr = document.createElement('hr')
      hr.id = id
      hr.setAttribute('data-xt-sep', '')
      hr.className = 'mx-2 my-1 border-outline-gray-1'
      anchor.insertAdjacentElement('afterend', hr)
      anchor = hr
      return
    }

    const id = `crm-xt-sb-${item.type}-${item.label.replace(/[^a-z0-9]/gi, '-').toLowerCase()}`
    if (document.getElementById(id)) {
      anchor = document.getElementById(id)
      return
    }

    // ── Group (collapsible section) ──────────────────────────────────────────
    if (item.type === 'group') {
      const wrapper = document.createElement('div')
      wrapper.id = id
      wrapper.classList.add('crm-xt')

      const icon = item.icon || 'folder'
      const nativeLabel = findNativeSectionLabel(document)
      let headerBtn
      if (nativeLabel) {
        headerBtn = cloneNativeSectionLabel(nativeLabel, { label: item.label })
      } else if (isModernSidebar(document)) {
        headerBtn = createSectionLabel(item.label)
      } else {
        headerBtn = document.createElement('button')
        headerBtn.className = callLogsBtn.className
        headerBtn.classList.add('crm-xt')
        headerBtn.innerHTML = `
        <div data-xt-inner class="flex w-full items-center justify-between duration-300 ease-in-out px-2 py-[7px]">
          <div class="flex items-center truncate">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
              stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
              class="flex items-center size-4 text-ink-gray-8">
              ${lucideIconInner(icon)}
            </svg>
            <span data-xt-label="margin"
              class="flex-1 flex-shrink-0 truncate text-sm duration-300 ease-in-out ml-2 w-auto opacity-100"
            >${item.label}</span>
          </div>
          <svg data-xt-hide-collapsed class="crm-xt-chevron size-4 text-ink-gray-5 transition-transform duration-200"
            viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </div>
      `
      }
      headerBtn.setAttribute('aria-label', item.label)
      headerBtn.setAttribute('aria-expanded', 'false')

      const childrenEl = document.createElement('nav')
      childrenEl.setAttribute('data-xt-children', '')
      childrenEl.className = 'flex flex-col gap-1'
      childrenEl.style.display = 'none'

      // Build child items
      ;(item.items || []).forEach((child) => {
        if (child.type === 'separator') {
          const hr = document.createElement('hr')
          hr.setAttribute('data-xt-sep', '')
          hr.className = 'mx-2 my-1 border-outline-gray-1'
          childrenEl.appendChild(hr)
          return
        }
        const childBtn = _makeSidebarBtn(child)
        childrenEl.appendChild(childBtn)
      })

      // Toggle collapse — only works when sidebar is expanded
      headerBtn.addEventListener('click', () => {
        if (_isSidebarCollapsed()) return
        const expanded = headerBtn.getAttribute('aria-expanded') === 'true'
        headerBtn.setAttribute('aria-expanded', String(!expanded))
        const chevron = headerBtn.querySelector('.crm-xt-chevron')
        const openRotation = chevron?.classList.contains('lucide-chevron-right')
          ? 'rotate(90deg)'
          : 'rotate(180deg)'
        if (!expanded) {
          childrenEl.style.display = 'flex'
          if (chevron) chevron.style.transform = openRotation
        } else {
          childrenEl.style.display = 'none'
          if (chevron) chevron.style.transform = ''
        }
        _syncCollapse()
      })

      wrapper.appendChild(headerBtn)
      wrapper.appendChild(childrenEl)
      anchor.insertAdjacentElement('afterend', wrapper)
      anchor = wrapper
      return
    }

    // ── list_view / route ────────────────────────────────────────────────────
    const btn = _makeSidebarBtn(item)
    btn.id = id
    anchor.insertAdjacentElement('afterend', btn)
    anchor = btn
  })

  // Wire up collapse sync after all elements are in the DOM
  _setupCollapseObserver()
  _syncCollapse()
  _syncActiveRow()
}

// ── Events tab injection ─────────────────────────────────────────────────────
// FCRM doesn't have an Events tab.  We:
//   1. Inject a fake "Events" tab button into the tablist
//   2. When clicked, mount InjectedEventsTab inside an absolute overlay that
//      covers the live tabpanel (the tabpanel always stays in the DOM because
//      Activities component owns it — we just paint on top)
//   3. When any real Reka tab is clicked, remove the overlay

let _xtEventsApp = null // the Vue app instance
let _xtEventsEl = null // the overlay <div>
let _xtEventsTabBtn = null // our injected <button>
// eslint-disable-next-line @typescript-eslint/no-unused-vars
let _prevActiveTab = null // native Reka tab that was active before overlay
const _listenedTablists = new WeakSet()

function _getCurrentDocInfo() {
  const m = window.location.pathname.match(/\/crm\/(leads|deals)\/([^?#/]+)/)
  if (!m) return null

  // Skip view/list pages - only inject on actual detail pages
  // This excludes paths like /crm/leads/view/*, /crm/deals/view/*, etc.
  const docname = decodeURIComponent(m[2])
  if (docname === 'view') return null

  return {
    doctype: m[1] === 'leads' ? 'CRM Lead' : 'CRM Deal',
    docname: docname,
  }
}

// Matches frappe-ui's inactive tab label (text-ink-gray-5)
const _TAB_INACTIVE_COLOR = 'var(--ink-gray-5,#7c7c7c)'

function _removeEventsOverlay() {
  if (_xtEventsApp) {
    _xtEventsApp.unmount()
    _xtEventsApp = null
  }
  if (_xtEventsEl?.parentNode) {
    _xtEventsEl.parentNode.removeChild(_xtEventsEl)
    _xtEventsEl = null
  }
  if (_xtEventsTabBtn) {
    _xtEventsTabBtn.setAttribute('data-state', 'inactive')
    _xtEventsTabBtn.style.color = _TAB_INACTIVE_COLOR
  }
  _prevActiveTab = null
  // Restore the Reka indicator to the currently-active native tab
  _syncRekaIndicator()
}

function _getVisiblePanel() {
  // There are 8 tabpanels (one per tab).  Only the active one is visible.
  return (
    Array.from(document.querySelectorAll('[role="tabpanel"]')).find(
      (p) => !p.hasAttribute('hidden') && p.offsetHeight > 0,
    ) || document.querySelector('[role="tabpanel"]:not([hidden])')
  )
}

// Move the Reka TabsIndicator to point at a given button.
// If no button supplied, let Reka re-compute it for the currently active native tab
// by briefly toggling a CSS transition so it snaps back naturally.
function _syncRekaIndicator(targetBtn) {
  const tablist =
    (
      _xtEventsTabBtn || document.querySelector('[data-xt-events-tab]')
    )?.closest('[role="tablist"]') || document.querySelector('[role="tablist"]')
  if (!tablist) return

  const indicator = tablist.querySelector('div[style*="--reka-tabs-indicator"]')
  if (!indicator) return

  // The tab's text colour lives on its inner Pill span, not the button
  const activeNative = tablist.querySelector(
    '[role="tab"][data-state="active"]',
  )
  const activeLabel =
    activeNative?.querySelector('[data-state]') || activeNative
  if (targetBtn) {
    // Moving indicator to our button — dim the native active tab
    if (activeLabel) activeLabel.style.color = _TAB_INACTIVE_COLOR
  } else {
    // Restoring — un-dim native tab and point the indicator at it
    if (activeLabel) activeLabel.style.color = ''
    if (_xtEventsTabBtn) _xtEventsTabBtn.style.color = _TAB_INACTIVE_COLOR
  }
  // Measure the tab now: Reka may already have moved to a newly clicked tab
  const btn = targetBtn || activeNative
  if (!btn) return
  const tablistRect = tablist.getBoundingClientRect()
  const btnRect = btn.getBoundingClientRect()
  const pos = btnRect.left - tablistRect.left + tablist.scrollLeft
  indicator.style.setProperty(
    '--reka-tabs-indicator-size',
    btnRect.width + 'px',
  )
  indicator.style.setProperty('--reka-tabs-indicator-position', pos + 'px')
}

function _showEventsOverlay(doctype, docname) {
  _removeEventsOverlay()

  const panel = _getVisiblePanel()
  if (!panel) return

  panel.style.position = 'relative'

  const overlay = document.createElement('div')
  overlay.setAttribute('data-xt-events-overlay', '')
  overlay.style.cssText =
    'position:absolute;inset:0;z-index:19;overflow:hidden;' +
    'background:var(--surface-base,#ffffff);'
  panel.appendChild(overlay)
  _xtEventsEl = overlay

  // eslint-disable-next-line vue/one-component-per-file -- createApp mount, not a component definition
  _xtEventsApp = createApp(InjectedEventsTab, { doctype, docname })
  _xtEventsApp.mount(overlay)

  // Move the native Reka TabsIndicator to sit under our button — identical appearance,
  // zero CSS hacks. Also dim the native active tab text so it looks inactive.
  if (_xtEventsTabBtn) {
    _xtEventsTabBtn.setAttribute('data-state', 'active')
    _xtEventsTabBtn.style.color = 'var(--ink-gray-9,#1c1c1c)'
    _syncRekaIndicator(_xtEventsTabBtn)
  }
}

function _tryInjectEventsTab() {
  const docInfo = _getCurrentDocInfo()
  // Not on a Lead/Deal detail page — clean up and stop
  if (!docInfo) {
    _removeEventsOverlay()
    _xtEventsTabBtn = null
    return
  }

  const tablist = document.querySelector('[role="tablist"]')
  if (!tablist) return

  // Register click listener on this tablist once only
  if (!_listenedTablists.has(tablist)) {
    _listenedTablists.add(tablist)
    tablist.addEventListener(
      'click',
      (e) => {
        // Any click on a real Reka tab (not our button) dismisses the overlay
        const t = e.target.closest('[role="tab"]')
        if (t) {
          _removeEventsOverlay()
        }
      },
      true, // capture — fires before Reka's own handler
    )
  }

  // Re-use an already-injected button (handles re-render by FCRM)
  const existing = tablist.querySelector('[data-xt-events-tab]')
  if (existing) {
    _xtEventsTabBtn = existing
    return
  }

  // Clone className from the first real tab so we match FCRM's styling exactly.
  // NOTE: do NOT set role="tab" — Reka would intercept the click and collapse
  // the tabpanel (setting its height to 0), making our overlay invisible.
  const refTab = tablist.querySelector('[role="tab"]')
  if (!refTab) return

  const btn = document.createElement('button')
  btn.setAttribute('type', 'button')
  btn.setAttribute('data-xt-events-tab', '')
  btn.setAttribute('data-state', 'inactive')
  btn.className = refTab.className
  btn.style.color = _TAB_INACTIVE_COLOR

  // Calendar icon + label — matches the icon+text structure of other tabs
  btn.innerHTML =
    '<span style="display:flex;align-items:center;gap:6px;">' +
    '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor"' +
    ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">' +
    '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>' +
    '<line x1="16" y1="2" x2="16" y2="6"/>' +
    '<line x1="8" y1="2" x2="8" y2="6"/>' +
    '<line x1="3" y1="10" x2="21" y2="10"/>' +
    '</svg>Events</span>'

  btn.addEventListener('click', () => {
    const di = _getCurrentDocInfo()
    if (di) _showEventsOverlay(di.doctype, di.docname)
  })

  tablist.appendChild(btn)
  _xtEventsTabBtn = btn
}

// ── Notification helper (matches frappe-ui toast styling) ─────────────────────
function _showNotification(message, type = 'info') {
  // Frappe-UI toast: dark bg, bottom-right, rounded
  const iconSvg =
    type === 'success'
      ? '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
      : type === 'error'
        ? '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'
        : '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'

  const notify = document.createElement('div')
  notify.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: var(--surface-gray-9, #1f2937);
    color: white;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 400;
    z-index: 100;
    max-width: 400px;
    min-width: 280px;
    box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1);
    display: flex;
    align-items: center;
    gap: 8px;
    pointer-events: auto;
    animation: crm-xt-toast-in 0.2s ease-out;
  `
  notify.innerHTML =
    iconSvg +
    '<span>' +
    message.replace(/</g, '&lt;').replace(/>/g, '&gt;') +
    '</span>'

  // Add animation keyframes if not already present
  if (!document.getElementById('crm-xt-toast-style')) {
    const style = document.createElement('style')
    style.id = 'crm-xt-toast-style'
    style.textContent = `
      @keyframes crm-xt-toast-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
      @keyframes crm-xt-toast-out { from { opacity: 1; transform: translateY(0); } to { opacity: 0; transform: translateY(8px); } }
    `
    document.head.appendChild(style)
  }

  document.body.appendChild(notify)
  setTimeout(() => {
    notify.style.animation = 'crm-xt-toast-out 0.2s ease-in forwards'
    setTimeout(() => notify.remove(), 200)
  }, 3000)
}

// Expose globally so any XT module-level code can use it
window.$toast = {
  success: (msg) => _showNotification(msg, 'success'),
  error: (msg) => _showNotification(msg, 'error'),
  warning: (msg) => _showNotification(msg, 'warning'),
  info: (msg) => _showNotification(msg, 'info'),
}

// ── Follow button injection ──────────────────────────────────────────────────
let _followState = {}

async function _loadFollowState(doctype, docname) {
  const resp = await fetch(
    `/api/method/frappe_crm_xt.api.follow.is_document_followed`,
    {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-Frappe-CSRF-Token': csrf(),
        Accept: 'application/json',
      },
      body: JSON.stringify({ doctype, doc_name: docname }),
    },
  )
  const data = await resp.json()
  const isFollowing = data?.message || false
  _followState[`${doctype}::${docname}`] = isFollowing
  return isFollowing
}

async function _toggleFollow(btn, doctype, docname) {
  try {
    const key = `${doctype}::${docname}`
    const currentState = _followState[key] || false
    const newState = !currentState

    const resp = await fetch(
      `/api/method/frappe_crm_xt.api.follow.update_follow`,
      {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-Frappe-CSRF-Token': csrf(),
          Accept: 'application/json',
        },
        body: JSON.stringify({
          doctype,
          doc_name: docname,
          following: newState,
        }),
      },
    )

    const data = await resp.json()

    // Extract message from _server_messages (contains actual success/error)
    let statusMsg = null
    const serverMsgs = data?._server_messages || data?.data?._server_messages
    if (serverMsgs) {
      try {
        const raw =
          typeof serverMsgs === 'string' ? JSON.parse(serverMsgs) : serverMsgs
        const first = Array.isArray(raw) ? raw[0] : raw
        const parsed = typeof first === 'string' ? JSON.parse(first) : first
        statusMsg = parsed.message
      } catch (err) {
        // _server_messages shape is unpredictable across Frappe versions; the
        // fallback below picks up `data.message`. Log at debug level — not an
        // app-breaking failure but useful when triaging unexpected payloads.
        console.debug('[crm-xt] _server_messages parse fallback:', err)
      }
    }

    // Fallback to top-level message if string
    if (!statusMsg && typeof data?.message === 'string') {
      statusMsg = data.message
    }

    // Determine if success or error based on status message content
    const isError =
      statusMsg &&
      (statusMsg.includes('not enabled') ||
        statusMsg.includes('error') ||
        statusMsg.includes('Error'))

    if (statusMsg && !isError) {
      // Success case - update state and icon
      _followState[key] = newState
      _updateFollowBtnIcon(btn, newState)
      _showNotification(statusMsg, 'success')
      return
    }

    if (statusMsg && isError) {
      // Error case - show error message
      _showNotification(statusMsg, 'error')
      return
    }

    // Fallback for no message
    if (resp.ok && data?.message === 1) {
      // message is 1 but no status msg - likely success
      _followState[key] = newState
      _updateFollowBtnIcon(btn, newState)
      _showNotification(newState ? 'Following' : 'Unfollowed', 'success')
      return
    }

    _showNotification('Unable to update follow status', 'error')
  } catch (err) {
    _showNotification('Follow error: ' + err.message, 'error')
  }
}

function _updateFollowBtnIcon(btn, isFollowing) {
  if (!btn) return
  // Eye filled icon if following, eye outline if not
  const eyeSvg = isFollowing
    ? '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none" class="h-4"><path d="M12 5C7 5 2.73 8.11 1 12.46c1.73 4.35 6 7.54 11 7.54s9.27-3.19 11-7.54C21.27 8.11 17 5 12 5zm0 12.5c-2.49 0-4.5-2.01-4.5-4.5S9.51 8.5 12 8.5s4.5 2.01 4.5 4.5-2.01 4.5-4.5 4.5zm0-7c-1.38 0-2.5 1.12-2.5 2.5s1.12 2.5 2.5 2.5 2.5-1.12 2.5-2.5-1.12-2.5-2.5-2.5z"/></svg>'
    : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>'
  btn.innerHTML = eyeSvg
}

function _tryInjectFollowBtn() {
  const docInfo = _getCurrentDocInfo()
  if (!docInfo) return

  // Re-use existing button if it still exists in DOM
  let existing = document.querySelector('[data-xt-follow-btn]')
  if (existing && existing.parentElement) return

  // Find the icon row by looking for a container with exactly 4 small icon buttons
  // (email, link, paperclip, delete) which is the standard FCRM lead/deal icon row
  let iconRow = null

  // Get all elements and check each one
  const allElements = Array.from(document.querySelectorAll('*'))

  for (const el of allElements) {
    // Count direct button children
    const directButtonChildren = Array.from(el.children).filter(
      (ch) => ch.tagName === 'BUTTON',
    )

    // The icon row should have 4 buttons (the standard FCRM icon set)
    if (directButtonChildren.length !== 4) continue

    // All buttons should be small (icon size, not action size)
    const allSmallButtons = directButtonChildren.every((btn) => {
      return btn.offsetWidth < 60 && btn.offsetHeight < 60
    })

    if (allSmallButtons) {
      iconRow = el
      break
    }
  }

  if (!iconRow) {
    return
  }

  // Get reference button for styling
  const refBtn = iconRow.querySelector('button')
  if (!refBtn) {
    return
  }

  // Create new button
  const btn = document.createElement('button')
  btn.setAttribute('type', 'button')
  btn.setAttribute('data-xt-follow-btn', '')
  btn.setAttribute('aria-label', 'Follow')
  btn.className = refBtn.className
  btn.style.cursor = 'pointer'

  // Show outline eye by default while loading
  _updateFollowBtnIcon(btn, false)

  // Load follow state and update icon
  _loadFollowState(docInfo.doctype, docInfo.docname)
    .then((isFollowing) => {
      _updateFollowBtnIcon(btn, isFollowing)
    })
    .catch((err) => {
      // Follow state lookup failed (network/perms). UI keeps the optimistic
      // "not following" icon. Log so the failure is visible.
      console.warn('[crm-xt] Failed to load follow state:', err)
    })

  // Click handler
  btn.addEventListener('click', (e) => {
    e.preventDefault()
    _toggleFollow(btn, docInfo.doctype, docInfo.docname)
  })

  // Append to icon row
  iconRow.appendChild(btn)
}

// ── Tab Change Detection ────────────────────────────────────────────────────
// Re-inject follow button when tabs are switched (Activity, Todos, Attachments, etc.)
function setupTabObserver() {
  const observer = new MutationObserver(() => {
    // Check if follow button exists
    const existing = document.querySelector('[data-xt-follow-btn]')

    // If button doesn't exist, re-inject it
    if (!existing && _getCurrentDocInfo()) {
      _tryInjectFollowBtn()
    }
  })

  // Observe the entire document for changes (more aggressive)
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true, // Also watch attribute changes
    attributeOldValue: false,
    characterData: false,
  })

  return observer
}

// ── Mount ───────────────────────────────────────────────────────────────────
onMounted(() => {
  // Only set up follow button injection on detail pages
  const isOnDetailPage = !!_getCurrentDocInfo()
  let pollInterval = null
  let tabObserver = null

  function setupFollowButtonHandlers() {
    // Setup tab observer to re-inject button on tab changes
    tabObserver = setupTabObserver()

    // Polling mechanism to ensure button always exists (fallback)
    // Only run this on detail pages
    if (!pollInterval) {
      pollInterval = setInterval(() => {
        const docInfo = _getCurrentDocInfo()
        if (docInfo) {
          const existing = document.querySelector('[data-xt-follow-btn]')
          if (!existing) {
            _tryInjectFollowBtn()
          }
        }
      }, 300) // Check every 300ms for faster detection
    }
  }

  // Only initialize if on a detail page
  if (isOnDetailPage) {
    setupFollowButtonHandlers()
  }

  loadSidebarItems() // fetches items → injects custom buttons + FCRM route

  // Re-inject on navigation (FCRM rebuilds sidebar on route changes)
  let reinjectTimer = null
  const onPopstate = () => {
    clearTimeout(reinjectTimer)
    reinjectTimer = setTimeout(() => {
      injectCustomSidebarBtns()
      _syncActiveRow()
      _tryInjectEventsTab()
      // Only inject follow button if on a detail page
      if (_getCurrentDocInfo()) {
        _tryInjectFollowBtn()
      }
    }, 250)
  }
  window.addEventListener('popstate', onPopstate)

  // MutationObserver: re-inject if FCRM Vue router rebuilds the sidebar
  const obs = new MutationObserver(() => {
    if (sidebarItems.value.length) {
      // Find first item with a label (separators have none)
      const firstLabeled = sidebarItems.value.find((i) => i.label)
      const firstId = firstLabeled
        ? `crm-xt-sb-${firstLabeled.type}-${firstLabeled.label.replace(/[^a-z0-9]/gi, '-').toLowerCase()}`
        : 'crm-xt-sb-sep-0'
      if (!document.getElementById(firstId)) injectCustomSidebarBtns()
    }
    _syncActiveRow()
    // Try to inject events tab whenever DOM changes (tab switches, navigation)
    _tryInjectEventsTab()
    // Try to inject follow button whenever DOM changes (only on detail pages)
    if (_getCurrentDocInfo()) {
      _tryInjectFollowBtn()
    }
  })
  obs.observe(document.body, { childList: true, subtree: true })

  onUnmounted(() => {
    obs.disconnect()
    tabObserver?.disconnect()
    _teardownCollapseObserver()
    clearInterval(pollInterval)
    clearTimeout(reinjectTimer)
    window.removeEventListener('popstate', onPopstate)
  })
})
</script>
