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
          <div class="flex items-center gap-2 px-4 py-3">
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

            <Popover placement="bottom-end">
              <template #target="{ togglePopover }">
                <Button @click="togglePopover()">
                  {{
                    activeFilters.length
                      ? `${activeFilters.length} type${activeFilters.length === 1 ? '' : 's'}`
                      : 'All types'
                  }}
                </Button>
              </template>
              <template #body="{ close: closePopover }">
                <div
                  class="crm-xt-search-filters my-2 w-44 p-1.5 rounded-lg bg-surface-elevation-2 shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none"
                >
                  <div
                    v-for="f in FILTERS"
                    :key="f.key"
                    class="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-surface-gray-2 cursor-pointer"
                    @click="toggleFilter(f.key)"
                  >
                    <span
                      class="flex h-4 w-4 shrink-0 items-center justify-center rounded transition-colors"
                      :class="
                        activeFilters.includes(f.key)
                          ? 'bg-surface-gray-10'
                          : 'border border-outline-gray-4'
                      "
                    >
                      <span
                        v-if="activeFilters.includes(f.key)"
                        class="text-ink-base"
                        v-html="sizedIcon('check', 'size-3')"
                      ></span>
                    </span>
                    <span class="text-sm text-ink-gray-7">{{ f.label }}</span>
                  </div>
                  <div
                    v-if="activeFilters.length"
                    class="border-t border-outline-gray-1 mt-1 pt-1"
                  >
                    <button
                      type="button"
                      class="w-full text-left rounded px-2 py-1.5 text-sm text-ink-gray-5 hover:bg-surface-gray-2"
                      @click="clearFilters(closePopover)"
                    >
                      Clear filters
                    </button>
                  </div>
                </div>
              </template>
            </Popover>
          </div>

          <hr />

          <!-- ── Results ── -->
          <div class="p-2 max-h-96 overflow-y-auto">
            <ul v-if="results.length" class="flex flex-col gap-1">
              <li
                v-for="(result, i) in results"
                :key="result.doctype + '::' + result.name"
                class="flex items-start gap-3 py-2 px-2 cursor-pointer rounded-lg"
                :class="
                  activeIdx === i
                    ? 'bg-surface-gray-2'
                    : 'hover:bg-surface-gray-2'
                "
                @click="selectResult(result)"
                @mouseenter="activeIdx = i"
              >
                <div class="min-w-0 flex-1">
                  <div
                    class="flex items-center gap-2 text-base text-ink-gray-8 truncate"
                  >
                    <span class="truncate">{{
                      result.title || result.name
                    }}</span>
                    <span
                      v-if="result.doctype === 'Converted Lead'"
                      class="inline-flex items-center gap-1 shrink-0 text-xs font-medium text-ink-green-9"
                      title="Converted"
                    >
                      <span v-html="sizedIcon('circle-check', 'size-3')"></span>
                      Converted
                    </span>
                  </div>
                  <!-- eslint-disable vue/no-v-html -- server-sanitised excerpt with <mark> highlights -->
                  <div
                    class="text-sm text-ink-gray-5 truncate"
                    v-html="result.excerpt"
                  ></div>
                  <!-- eslint-enable vue/no-v-html -->
                </div>
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
import { Popover, Button } from 'frappe-ui'
import { getLucideIcon } from '../lucideIcons'

const PAGE_SIZE = 20

// The host crm app's Tailwind build never sees this file, so only utility
// classes it already generates elsewhere actually render here — arbitrary
// variants like `[&_svg]:h-3` are never in that set. lucide-static's raw SVGs
// hardcode width/height="24", so strip those and put a real `size-N` class
// straight on the <svg> (mirrors utils/sidebarRow.js's buildIconSvg).
function sizedIcon(name, sizeClass) {
  return getLucideIcon(name)
    .replace(/\s(width|height)="[^"]*"/g, '')
    .replace(/class="([^"]*)"/, `class="$1 ${sizeClass}"`)
}

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

let offset = 0
let debounceTimer = null
let inflight = null

// ── Search filters (mirrors backend SEARCH_FILTERS keys in api/search.py) ───
// Multi-select: an empty selection means "All".
const FILTERS = [
  { key: 'CRM Lead', label: 'Lead' },
  { key: 'Converted Lead', label: 'Converted' },
  { key: 'CRM Deal', label: 'Deal' },
  { key: 'CRM Organization', label: 'Organization' },
  { key: 'FCRM Note', label: 'Note' },
  { key: 'CRM Task', label: 'Task' },
  { key: 'Contact', label: 'Contact' },
]

const activeFilters = ref([])

function toggleFilter(key) {
  activeFilters.value = activeFilters.value.includes(key)
    ? activeFilters.value.filter((k) => k !== key)
    : [...activeFilters.value, key]
  doSearch(false)
}

function clearFilters(closePopover) {
  activeFilters.value = []
  doSearch(false)
  closePopover()
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
      activeFilters.value = []
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
    return
  }
  if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIdx.value = Math.max(activeIdx.value - 1, 0)
    return
  }
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
      doctypes: activeFilters.value.length ? activeFilters.value : null,
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

<style>
/* frappe-ui's Popover teleports its panel to <body> with a hardcoded z-[100],
   which lands underneath this dialog's z-index: 9999 overlay — the dropdown
   opens but is invisible/unclickable. :has() scopes the fix to just our own
   filter popover (via the marker class below) so no other Popover in the
   host app is affected, and this being unscoped/unlayered CSS already beats
   Tailwind's @layer utilities regardless of selector specificity. */
[data-slot='content']:has(.crm-xt-search-filters) {
  z-index: 10000;
}
</style>
