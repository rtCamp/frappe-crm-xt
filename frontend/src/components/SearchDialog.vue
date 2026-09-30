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
          class="my-8 inline-block w-full transform overflow-hidden rounded-xl bg-surface-elevation-2 text-left align-middle shadow-xl focus-visible:outline-none max-w-xl"
          role="dialog"
          aria-label="CRM Search"
          style="pointer-events: auto"
        >
          <!-- ── Input ── -->
          <div class="flex items-center">
            <div class="relative flex items-center mx-4 py-3 flex-1">
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
                class="text-base rounded h-7 py-1.5 pl-8 pr-2 border border-outline-gray-2 bg-surface-base placeholder-ink-gray-4 hover:border-outline-gray-3 hover:shadow-sm focus:bg-surface-base focus:border-outline-gray-4 focus:shadow-sm focus:ring-0 focus-visible:ring-2 focus-visible:ring-outline-gray-3 text-ink-gray-8 transition-colors w-full"
                @keydown="handleKeyDown"
                @input="onInput"
              />
            </div>
          </div>

          <!-- ── Doctype filters ── -->
          <div
            v-if="availableDoctypes.length"
            class="flex items-center gap-1 px-4 pb-3 flex-wrap"
          >
            <button
              v-if="multiSelect"
              type="button"
              class="rounded px-2 py-1 text-xs transition-colors"
              :aria-pressed="activeDoctypes.length === 0"
              :class="
                activeDoctypes.length === 0
                  ? 'bg-surface-gray-3 text-ink-gray-9'
                  : 'bg-surface-gray-1 text-ink-gray-5 hover:bg-surface-gray-2'
              "
              @click="selectAll"
            >
              All
            </button>
            <button
              v-for="dt in availableDoctypes"
              :key="dt"
              type="button"
              class="rounded px-2 py-1 text-xs transition-colors"
              :aria-pressed="isDoctypeActive(dt)"
              :class="
                isDoctypeActive(dt)
                  ? 'bg-surface-gray-3 text-ink-gray-9'
                  : 'bg-surface-gray-1 text-ink-gray-5 hover:bg-surface-gray-2'
              "
              @click="toggleDoctype(dt)"
            >
              {{ dtLabel(dt) }}
            </button>
          </div>

          <hr />

          <!-- ── Results ── -->
          <div class="p-2 max-h-96 overflow-y-auto">
            <ul v-if="results.length" class="flex flex-col gap-0.5">
              <li
                v-for="(result, i) in results"
                :key="result.doctype + '::' + result.name"
                class="flex items-center gap-3 py-2 px-2 cursor-pointer rounded-lg"
                :class="
                  activeIdx === i
                    ? 'bg-surface-gray-2'
                    : 'hover:bg-surface-gray-2'
                "
                @click="selectResult(result)"
                @mouseenter="activeIdx = i"
              >
                <Avatar :label="result.title || result.name" size="lg" />
                <div class="min-w-0 flex-1 text-left">
                  <div class="text-base text-ink-gray-8 truncate">
                    {{ result.title || result.name }}
                  </div>
                  <div
                    v-for="(field, fi) in result.fields"
                    :key="fi"
                    class="flex items-baseline gap-1 text-sm"
                  >
                    <span v-if="field.label" class="shrink-0 text-ink-gray-4"
                      >{{ field.label }}:</span
                    >
                    <!-- eslint-disable vue/no-v-html -- server-sanitised field value with <mark> highlights -->
                    <span
                      class="truncate text-ink-gray-6"
                      v-html="field.value"
                    ></span>
                    <!-- eslint-enable vue/no-v-html -->
                  </div>
                </div>
                <Badge
                  :label="badgeLabel(result)"
                  theme="gray"
                  size="sm"
                  class="shrink-0"
                />
              </li>
            </ul>

            <div
              v-else-if="query.length > 0 && !loading"
              class="text-sm text-ink-gray-5 text-center py-4"
            >
              No results for
              <strong class="text-ink-gray-8">{{ query }}</strong>
            </div>
            <div
              v-else-if="loading"
              class="text-sm text-ink-gray-5 text-center py-4"
            >
              Searching…
            </div>
            <div v-else class="py-4">
              <p class="text-xs text-ink-gray-4 text-center">
                Type to search leads, deals, contacts…
              </p>
            </div>
          </div>

          <hr />

          <!-- ── Footer ── -->
          <div class="flex items-center justify-between px-4 h-12">
            <div>
              <p v-if="results.length" class="text-xs text-ink-gray-5">
                <b>{{ results.length }}</b> result{{
                  results.length === 1 ? '' : 's'
                }}
                found
              </p>
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

// ── Route map (handles both native FCRM and bridge doctype names) ───────────
const ROUTES = {
  'CRM Lead': (n) => ({ path: `/crm/leads/${encodeURIComponent(n)}` }),
  Lead: (n) => ({ path: `/app/lead/${encodeURIComponent(n)}` }),
  'CRM Deal': (n) => ({ path: `/crm/deals/${encodeURIComponent(n)}` }),
  Contact: (n) => ({ path: `/crm/contacts/${encodeURIComponent(n)}` }),
  'CRM Organization': (n) => ({
    path: `/crm/organizations/${encodeURIComponent(n)}`,
  }),
  'FCRM Note': () => ({ path: `/crm/notes/view/list` }),
  'CRM Call Log': () => ({ path: `/crm/call-logs/view/list` }),
}

function routeFor(doctype, name) {
  const fn = ROUTES[doctype]
  return fn ? fn(name) : null
}

// ── Doctype labels ───────────────────────────────────────────────────────────
const DT_LABELS = {
  'CRM Lead': 'Lead',
  Lead: 'ERP Lead',
  'CRM Deal': 'Deal',
  Opportunity: 'ERP Deal',
  Contact: 'Contact',
  'CRM Organization': 'Org',
  'FCRM Note': 'Note',
  Event: 'Calendar',
  'CRM Call Log': 'Call',
}

function dtLabel(dt) {
  return DT_LABELS[dt] || dt
}

// A Lead result carries its own `converted` flag (see search.py), so it can
// be badged distinctly from an active lead.
function badgeLabel(result) {
  if (result.doctype === 'CRM Lead' && result.converted) return 'Converted'
  return dtLabel(result.doctype)
}

// ── Doctype filters ──────────────────────────────────────────────────────────
const availableDoctypes = ref([])
const multiSelect = ref(true)
const activeDoctypes = ref([])

function isDoctypeActive(dt) {
  return activeDoctypes.value.includes(dt)
}

function selectAll() {
  activeDoctypes.value = []
  doSearch(false)
}

function toggleDoctype(dt) {
  activeDoctypes.value = multiSelect.value
    ? activeDoctypes.value.includes(dt)
      ? activeDoctypes.value.filter((d) => d !== dt)
      : [...activeDoctypes.value, dt]
    : [dt]
  doSearch(false)
}

function fetchFilters() {
  fetch('/api/method/frappe_crm_xt.api.search.get_search_filters', {
    method: 'GET',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
    .then((r) => r.json())
    .then((data) => {
      availableDoctypes.value = data?.message?.filters || []
      multiSelect.value = !!data?.message?.multi
      // Single-select has no "All" — land on the first filter instead.
      activeDoctypes.value = multiSelect.value
        ? []
        : availableDoctypes.value.slice(0, 1)
      // A fast typist can already have searched (unfiltered) before this
      // resolves — rerun so results match the filter it just landed on.
      if (props.show && query.value) doSearch(false)
    })
    .catch(() => {})
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
      fetchFilters()
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
      limit: 20,
      doctypes: activeDoctypes.value.length ? activeDoctypes.value : null,
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
      offset += 20
    })
    .catch((err) => {
      if (err.name !== 'AbortError') results.value = []
    })
    .finally(() => {
      loading.value = false
    })
}

// ── Result mapping ───────────────────────────────────────────────────────────
// Splits "Label : value" so the label can be styled separately from the value.
function splitField(line) {
  const i = line.indexOf(':')
  if (i === -1) return { label: '', value: line }
  return { label: line.slice(0, i).trim(), value: line.slice(i + 1).trim() }
}

function mapResults(list) {
  const seen = new Set()
  return list
    .map((r) => {
      const title =
        r.title || extractTitle(r.content || r.marked_string || '') || r.name
      // One field per line — nothing collapsed or cut off.
      const fields = (r.marked_string || r.content || '')
        .split(/<br>\s*/gi)
        .map((line) => line.trim())
        .filter(Boolean)
        .map(splitField)
      return {
        title,
        fields,
        doctype: r.doctype,
        name: r.name,
        converted: !!r.converted,
      }
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
