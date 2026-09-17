<template>
  <Transition name="crm-xt-fade">
    <div
      v-if="show"
      class="fixed inset-0 overflow-y-auto outline-none"
      style="
        z-index: 9999;
        background: rgba(0, 0, 0, 0.28);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        pointer-events: auto;
      "
      @mousedown.self="close"
    >
      <div
        class="flex min-h-screen flex-col items-center px-4 py-4 text-center pt-[20vh]"
        @mousedown.self="close"
      >
        <div
          class="my-8 inline-block w-full transform overflow-hidden rounded-xl bg-surface-elevation-2 text-left align-middle shadow-xl ring-1 ring-black ring-opacity-5 focus-visible:outline-none max-w-2xl"
          role="dialog"
          aria-label="CRM Search"
          style="pointer-events: auto"
        >
          <!-- ── Input ── -->
          <div class="flex items-center px-4 py-3">
            <div class="relative flex items-center flex-1">
              <div
                class="absolute inset-y-0 left-0 flex items-center text-ink-gray-8 pl-3"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="shrink-0 h-4"
                >
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
              </div>
              <input
                id="crm-xt-search-input"
                ref="inputRef"
                v-model="query"
                type="text"
                name="crm-xt-search"
                placeholder="CRM Search"
                autocomplete="off"
                class="text-base rounded-lg h-7 py-1.5 pl-8 pr-2 border border-outline-gray-2 bg-surface-base placeholder-ink-gray-4 hover:border-outline-gray-3 hover:shadow-sm focus:bg-surface-base focus:border-outline-gray-4 focus:shadow-sm focus:ring-0 focus-visible:ring-2 focus-visible:ring-outline-gray-3 text-ink-gray-8 transition-colors w-full"
                @keydown="handleKeyDown"
                @input="onInput"
              />
            </div>
          </div>

          <!-- ── Type tabs ── -->
          <div
            class="flex items-center gap-1 px-2 py-1.5 border-b border-outline-gray-1 overflow-x-auto"
          >
            <button
              v-for="t in TABS"
              :key="t.key"
              type="button"
              class="rounded-md px-2.5 py-1.5 text-sm whitespace-nowrap transition-colors"
              :class="
                isTabActive(t.key)
                  ? 'bg-surface-gray-2 text-ink-gray-9'
                  : 'text-ink-gray-5 hover:bg-surface-gray-1 hover:text-ink-gray-7'
              "
              @click="selectTab(t.key)"
            >
              {{ t.label }}
            </button>
          </div>

          <!-- ── Results ── -->
          <div
            class="p-2 max-h-96 overflow-y-auto"
            @mousemove="ignoreHover = false"
          >
            <ul v-if="results.length" class="flex flex-col gap-1">
              <li
                v-for="(result, i) in results"
                :key="result.doctype + '::' + result.name"
                :ref="(el) => (resultRefs[i] = el)"
                class="flex items-center gap-3 py-2 px-2 cursor-pointer rounded-lg"
                :class="
                  activeIdx === i
                    ? 'bg-surface-gray-2'
                    : 'hover:bg-surface-gray-2'
                "
                @click="selectResult(result)"
                @mouseenter="hoverResult(i)"
              >
                <Avatar :label="result.title || result.name" size="sm" />
                <div class="min-w-0 flex-1">
                  <div class="text-base text-ink-gray-8 truncate">
                    {{ result.title || result.name }}
                  </div>
                  <!-- eslint-disable vue/no-v-html -- indexed field values are passed through
                       frappe.utils.strip_html_tags() in get_formatted_value() at document-save
                       time (frappe/utils/global_search.py), before ever reaching __global_search
                       .content — the only tags that can appear here are the <mark>/<br> this
                       excerpt intentionally adds itself, not attacker-controlled field values -->
                  <div
                    class="text-sm text-ink-gray-5 truncate"
                    v-html="result.excerpt"
                  ></div>
                  <!-- eslint-enable vue/no-v-html -->
                </div>
                <Badge
                  :label="TYPE_TAGS[result.doctype]?.label || result.doctype"
                  :theme="TYPE_TAGS[result.doctype]?.theme || 'gray'"
                  size="sm"
                  class="shrink-0"
                />
              </li>
            </ul>

            <div
              v-else-if="query.length > 0 && !loading"
              class="text-sm text-ink-gray-5 text-center py-10"
            >
              No results for
              <strong class="text-ink-gray-8">{{ query }}</strong>
            </div>
            <div
              v-else-if="loading"
              class="text-sm text-ink-gray-5 text-center py-10"
            >
              Searching…
            </div>
            <div v-else class="py-10">
              <p class="text-xs text-ink-gray-4 text-center">
                Type to search leads, deals, contacts…
              </p>
            </div>
          </div>

          <hr />

          <!-- ── Footer ── -->
          <div class="flex items-center justify-between px-4 h-12">
            <div class="flex items-center gap-4">
              <p v-if="results.length" class="text-xs text-ink-gray-5">
                <b>{{ results.length }}</b> result{{
                  results.length === 1 ? '' : 's'
                }}
                found
              </p>
              <div
                class="hidden sm:flex items-center gap-3 text-xs text-ink-gray-4"
              >
                <span class="flex items-center gap-1">
                  <kbd
                    class="font-mono text-xs rounded bg-surface-gray-2 px-1.5 py-0.5"
                    >↑↓</kbd
                  >
                  Navigate
                </span>
                <span class="flex items-center gap-1">
                  <kbd
                    class="font-mono text-xs rounded bg-surface-gray-2 px-1.5 py-0.5"
                    >↵</kbd
                  >
                  Select
                </span>
                <span class="flex items-center gap-1">
                  <kbd
                    class="font-mono text-xs rounded bg-surface-gray-2 px-1.5 py-0.5"
                    >Esc</kbd
                  >
                  Close
                </span>
              </div>
            </div>
            <div class="flex justify-center">
              <button
                v-if="hasMore"
                class="inline-flex items-center justify-center gap-2 transition-colors focus:outline-none text-ink-gray-8 bg-surface-gray-2 hover:bg-surface-gray-3 active:bg-surface-gray-4 focus-visible:ring focus-visible:ring-outline-gray-3 h-7 text-base px-2 rounded"
                @click="loadMore"
              >
                Load More
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { Avatar, Badge } from 'frappe-ui'

const PAGE_SIZE = 20

let domParser = null
const LIKELY_HTML_OR_ENTITY_RE = /<[a-zA-Z!/]|&[#a-zA-Z]/

const props = defineProps({
  show: Boolean,
})
const emit = defineEmits(['close', 'navigate'])

// ── State ──────────────────────────────────────────────────────────────────
const query = ref('')
const results = ref([])
const loading = ref(false)
const hasMore = ref(false)
const activeIdx = ref(0)
const inputRef = ref(null)
let resultRefs = []
// Arrow-key nav scrolls the list, which can leave the mouse cursor sitting
// over a *different* row without it actually moving — firing a spurious
// mouseenter there. Ignore hover-driven highlighting until the mouse moves
// for real again, so it can't fight the keyboard for activeIdx.
let ignoreHover = false

function hoverResult(i) {
  if (!ignoreHover) activeIdx.value = i
}

let offset = 0
let debounceTimer = null
let inflight = null

// ── Type tabs — each maps to one or more backend SEARCH_FILTERS keys ────────
// Leads and Converted are separate, non-overlapping tabs (mirrors the
// backend's CRM Lead vs Converted Lead split) so multi-select covers every
// case: just Leads, just Converted, or both together for all leads.
const TABS = [
  { key: 'all', label: 'All', filters: null },
  { key: 'leads', label: 'Leads', filters: ['CRM Lead'] },
  { key: 'converted', label: 'Converted', filters: ['Converted Lead'] },
  { key: 'deals', label: 'Deals', filters: ['CRM Deal'] },
  { key: 'orgs', label: 'Organizations', filters: ['CRM Organization'] },
  { key: 'notes', label: 'Notes', filters: ['FCRM Note'] },
  { key: 'tasks', label: 'Tasks', filters: ['CRM Task'] },
  { key: 'contacts', label: 'Contacts', filters: ['Contact'] },
]

// Multi-select: an empty selection (or picking "all") means "every type".
const activeTabs = ref([])

function isTabActive(key) {
  return key === 'all'
    ? activeTabs.value.length === 0
    : activeTabs.value.includes(key)
}

function selectTab(key) {
  if (key === 'all') {
    activeTabs.value = []
  } else {
    activeTabs.value = activeTabs.value.includes(key)
      ? activeTabs.value.filter((k) => k !== key)
      : [...activeTabs.value, key]
  }
  doSearch(false)
}

function activeFilters() {
  if (!activeTabs.value.length) return null
  const keys = new Set()
  for (const tabKey of activeTabs.value) {
    for (const f of TABS.find((t) => t.key === tabKey)?.filters ?? [])
      keys.add(f)
  }
  return [...keys]
}

// ── Type tags — how a result row shows whether it's a lead, deal, note... ──
const TYPE_TAGS = {
  'CRM Lead': { label: 'Lead', theme: 'blue' },
  'Converted Lead': { label: 'Converted', theme: 'green' },
  'CRM Deal': { label: 'Deal', theme: 'violet' },
  'CRM Organization': { label: 'Organization', theme: 'gray' },
  'FCRM Note': { label: 'Note', theme: 'gray' },
  'CRM Task': { label: 'Task', theme: 'amber' },
  Contact: { label: 'Contact', theme: 'gray' },
}

// ── Route map (handles both native FCRM and bridge doctype names) ───────────
const ROUTES = {
  'CRM Lead': (n) => ({ path: `/crm/leads/${encodeURIComponent(n)}` }),
  'Converted Lead': (n) => ({ path: `/crm/leads/${encodeURIComponent(n)}` }),
  Lead: (n) => ({ path: `/app/lead/${encodeURIComponent(n)}` }),
  'CRM Deal': (n) => ({ path: `/crm/deals/${encodeURIComponent(n)}` }),
  Contact: (n) => ({ path: `/crm/contacts/${encodeURIComponent(n)}` }),
  'CRM Organization': (n) => ({
    path: `/crm/organizations/${encodeURIComponent(n)}`,
  }),
  'FCRM Note': () => ({ path: `/crm/notes/view/list` }),
  'CRM Task': () => ({ path: `/crm/tasks/view/list` }),
  'CRM Call Log': () => ({ path: `/crm/call-logs/view/list` }),
}

function routeFor(doctype, name) {
  const fn = ROUTES[doctype]
  return fn ? fn(name) : null
}

// ── Lifecycle ───────────────────────────────────────────────────────────────
watch(
  () => props.show,
  (val) => {
    if (val) {
      query.value = ''
      results.value = []
      hasMore.value = false
      activeIdx.value = 0
      activeTabs.value = []
      nextTick(() => inputRef.value?.focus())
    }
  },
)

function close() {
  emit('close')
}

// ── Keyboard ────────────────────────────────────────────────────────────────
function handleKeyDown(e) {
  if (e.key === 'Escape') {
    e.preventDefault()
    close()
    return
  }
  if (e.key === 'Enter') {
    e.preventDefault()
    if (results.value[activeIdx.value]) {
      selectResult(results.value[activeIdx.value])
    } else if (query.value) {
      doSearch(false)
    }
    return
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIdx.value = Math.min(activeIdx.value + 1, results.value.length - 1)
    scrollActiveIntoView()
    return
  }
  if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIdx.value = Math.max(activeIdx.value - 1, 0)
    scrollActiveIntoView()
    return
  }
}

function scrollActiveIntoView() {
  ignoreHover = true
  nextTick(() =>
    resultRefs[activeIdx.value]?.scrollIntoView({ block: 'nearest' }),
  )
}

function onInput() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => doSearch(false), 250)
}

function loadMore() {
  doSearch(true)
}

// ── Search ──────────────────────────────────────────────────────────────────
function getCsrfToken() {
  return window.csrf_token || window.boot?.csrf_token || ''
}

function doSearch(append) {
  if (!query.value) {
    results.value = []
    hasMore.value = false
    return
  }
  if (!append) offset = 0
  if (inflight) {
    inflight.abort()
    inflight = null
  }

  loading.value = true
  const ctrl = new AbortController()
  inflight = ctrl

  fetch('/api/method/frappe_crm_xt.api.search.get_search_results', {
    method: 'POST',
    credentials: 'same-origin',
    signal: ctrl.signal,
    headers: {
      'Content-Type': 'application/json',
      'X-Frappe-CSRF-Token': getCsrfToken(),
      Accept: 'application/json',
    },
    body: JSON.stringify({
      text: query.value,
      start: offset,
      limit: PAGE_SIZE,
      doctypes: activeFilters(),
    }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (ctrl.signal.aborted) return
      // frappe_search returns message = [resultsArray, hasMoreBool]
      // fallback returns the same shape
      const raw = data?.message
      const list = Array.isArray(raw)
        ? Array.isArray(raw[0])
          ? raw[0]
          : raw
        : []
      hasMore.value = !!(Array.isArray(raw) && raw[1])
      results.value = append
        ? [...results.value, ...mapResults(list)]
        : mapResults(list)
      activeIdx.value = 0
      offset += PAGE_SIZE
    })
    .catch((err) => {
      if (err.name !== 'AbortError') results.value = []
    })
    .finally(() => {
      loading.value = false
    })
}

// ── Result mapping ───────────────────────────────────────────────────────────
function mapResults(list) {
  const seen = new Set()
  return list
    .map((r) => {
      const title =
        r.title || extractTitle(r.content || r.marked_string || '') || r.name
      const excerpt = r.marked_string || r.content || ''
      return { title, excerpt, doctype: r.doctype, name: r.name }
    })
    .filter((r) => {
      const key = `${r.doctype}::${r.name}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
}

// Extract human-readable title from frappe_search content strings like
// "Full Name : Alice Johnson ||| Name : CRM-LEAD-2026-00016"
function extractTitle(content) {
  const plain = htmlToPlainText(content)
  const patterns = [
    /Full Name\s*:\s*([^|\n]+)/i,
    /Organization Name\s*:\s*([^|\n]+)/i,
    /Subject\s*:\s*([^|\n]+)/i,
    /Title\s*:\s*([^|\n]+)/i,
    /First Name\s*:\s*([^|\n]+)/i,
    /Customer Name\s*:\s*([^|\n]+)/i,
  ]
  for (const re of patterns) {
    const m = plain.match(re)
    if (m) return m[1].trim()
  }
  return ''
}

function htmlToPlainText(html) {
  const text = String(html ?? '')
  if (!LIKELY_HTML_OR_ENTITY_RE.test(text)) return text
  if (typeof DOMParser === 'undefined') return text
  try {
    domParser ??= new DOMParser()
    const doc = domParser.parseFromString(text, 'text/html')
    return doc.body?.textContent || ''
  } catch {
    return text
  }
}

function selectResult(result) {
  const route = routeFor(result.doctype, result.name)
  close()
  if (route) emit('navigate', route)
  else
    window.open(
      `/app/${(result.doctype || '').toLowerCase().replace(/\s+/g, '-')}/${encodeURIComponent(result.name)}`,
      '_blank',
    )
}
</script>
