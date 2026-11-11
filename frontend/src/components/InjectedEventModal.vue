<template>
  <!-- Plain overlay — component is mounted directly to body by InjectedEventsTab -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black-overlay-200 dark:bg-black-overlay-700 dialog-overlay outline-none px-4 py-4"
    @click.self="emit('close')"
  >
    <div
      style="
        position: relative;
        width: 100%;
        max-width: 36rem;
        overflow: hidden;
        border-radius: 0.75rem;
        background: var(--surface-elevation-2, #ffffff);
        text-align: start;
        box-shadow:
          0 20px 25px -5px rgba(0, 0, 0, 0.1),
          0 8px 10px -6px rgba(0, 0, 0, 0.1);
      "
    >
      <div class="bg-surface-elevation-2 px-4 pb-6 pt-5 sm:px-6">
        <!-- Header -->
        <div class="mb-6 flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <h3 class="text-3xl-semibold leading-6 text-ink-gray-9">
              {{
                mode === 'edit'
                  ? __('Edit an Event')
                  : mode === 'duplicate'
                    ? __('Duplicate an Event')
                    : __('Create an Event')
              }}
            </h3>
          </div>
          <div class="flex gap-1">
            <Button v-if="mode === 'edit'" variant="ghost" @click="deleteEvent">
              <template #icon>
                <FeatherIcon name="trash-2" class="h-4 w-4 text-ink-gray-9" />
              </template>
            </Button>
            <Button
              v-if="mode === 'edit'"
              variant="ghost"
              @click="duplicateEvent"
            >
              <template #icon>
                <FeatherIcon name="copy" class="h-4 w-4 text-ink-gray-9" />
              </template>
            </Button>
            <Button variant="ghost" @click="emit('close')">
              <template #icon>
                <FeatherIcon name="x" class="h-4 w-4 text-ink-gray-9" />
              </template>
            </Button>
          </div>
        </div>

        <!-- Form fields -->
        <div class="flex flex-col gap-4">
          <div class="flex items-center">
            <div class="text-base text-ink-gray-7 w-3/12">
              {{ __('Title') }}
            </div>
            <div class="flex gap-1 w-9/12">
              <Dropdown :options="colors">
                <div
                  class="flex items-center justify-center size-7 shrink-0 border border-outline-gray-2 hover:border-outline-gray-3 hover:shadow-sm rounded cursor-pointer"
                >
                  <div
                    class="size-4 rounded-full"
                    :style="{ backgroundColor: _event.color || '#30A66D' }"
                  />
                </div>
              </Dropdown>
              <TextInput
                ref="titleRef"
                v-model="_event.title"
                class="w-full"
                size="sm"
                :placeholder="__('Call with John Doe')"
                variant="outline"
                required
              />
            </div>
          </div>

          <div class="flex items-center">
            <div class="text-base text-ink-gray-7 w-3/12">
              {{ __('All Day') }}
            </div>
            <Switch v-model="_event.isFullDay" />
          </div>

          <div class="border-t border-outline-gray-1" />

          <div class="flex items-center justify-between">
            <div class="text-base text-ink-gray-7 w-3/12">
              {{ __('Date & Time') }}
            </div>
            <div class="flex gap-2 w-9/12 justify-start fcrm-xt-datetime-row">
              <DatePicker
                class="w-[158px]"
                variant="outline"
                :value="_event.fromDate"
                :format="'MMM D, YYYY'"
                :placeholder="__('May 1, 2025')"
                :clearable="false"
                placement="bottom-end"
                @update:modelValue="(d) => updateDate(d)"
              >
                <template #suffix="{ togglePopover }">
                  <FeatherIcon
                    name="chevron-down"
                    class="h-4 w-4 cursor-pointer"
                    @click="togglePopover"
                  />
                </template>
              </DatePicker>
              <TimePicker
                v-if="!_event.isFullDay"
                class="max-w-[112px]"
                variant="outline"
                :modelValue="_event.fromTime"
                :placeholder="__('Start Time')"
                placement="bottom-end"
                @update:modelValue="(t) => updateTime(t, true)"
              />
              <TimePicker
                v-if="!_event.isFullDay"
                class="max-w-[112px]"
                variant="outline"
                :modelValue="_event.toTime"
                :options="toOptions"
                :placeholder="__('End Time')"
                placement="bottom-end"
                @update:modelValue="(t) => updateTime(t)"
              />
            </div>
          </div>

          <div class="flex items-start">
            <div class="text-base text-ink-gray-7 mt-1.5 w-3/12">
              {{ __('Attendees') }}
            </div>
            <div class="w-9/12">
              <Attendee
                v-model="peoples"
                :validate="validateEmail"
                :error-message="
                  (v) => __('{0} is an invalid email address', [v])
                "
              />
            </div>
          </div>

          <div class="flex items-start">
            <div class="text-base text-ink-gray-7 mt-1.5 w-3/12">
              {{ __('Visibility') }}
            </div>
            <div class="w-9/12 fcrm-xt-visibility-select">
              <FormControl
                v-model="_event.eventType"
                class="w-full"
                type="select"
                :options="[
                  { label: __('Private'), value: 'Private' },
                  { label: __('Public'), value: 'Public' },
                ]"
                variant="outline"
                :placeholder="__('Private or Public')"
              />
            </div>
          </div>

          <div class="flex items-start">
            <div class="text-base text-ink-gray-7 mt-1.5 w-3/12">
              {{ __('Location') }}
            </div>
            <div class="w-9/12">
              <TextInput
                v-model="_event.location"
                class="w-full"
                size="sm"
                variant="outline"
                :placeholder="__('Add Location')"
              />
            </div>
          </div>

          <div class="flex">
            <div class="mt-2 text-base text-ink-gray-7 w-3/12">
              {{ __('Description') }}
            </div>
            <div class="w-9/12">
              <TextEditor
                editor-class="!prose-sm overflow-auto min-h-[80px] max-h-80 py-1.5 px-2 rounded border border-outline-gray-2 placeholder-ink-gray-4 hover:border-outline-gray-3 hover:shadow-sm focus:bg-surface-base focus:border-outline-gray-4 focus:shadow-sm focus:ring-0 focus-visible:ring-2 focus-visible:ring-outline-gray-3 text-ink-gray-8 transition-colors"
                :bubbleMenu="true"
                :content="_event.description"
                :placeholder="__('Add Description.')"
                @change="(val) => (_event.description = val)"
              />
            </div>
          </div>

          <div class="border-t border-outline-gray-1" />

          <div class="flex">
            <div class="mt-1.5 text-base text-ink-gray-7 w-3/12">
              {{ __('Notifications') }}
            </div>
            <div class="w-9/12">
              <EventNotifications
                v-model="_event.notifications"
                :isAllDay="_event.isFullDay"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-4 pb-7 pt-4 sm:px-6">
        <div class="flex w-full items-center justify-between">
          <div>
            <ErrorMessage v-if="error" :message="__(error)" />
          </div>
          <div class="flex gap-2 justify-end">
            <Button :label="__('Cancel')" @click="emit('close')" />
            <Button
              variant="solid"
              :label="
                mode === 'edit'
                  ? __('Update')
                  : mode === 'duplicate'
                    ? __('Duplicate')
                    : __('Create')
              "
              :disabled="!dirty"
              :loading="saving"
              @click="update"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Dialog -->
    <Transition name="crm-xt-fade">
      <div
        v-if="showDeleteDialog"
        class="fixed inset-0 z-[60] flex items-center justify-center bg-black-overlay-200 dark:bg-black-overlay-700 outline-none"
        @click.self="cancelDelete"
      >
        <div
          class="my-8 inline-block w-full transform overflow-hidden rounded-xl bg-surface-elevation-2 text-left align-middle shadow-xl focus-visible:outline-none max-w-lg"
          role="dialog"
          aria-label="Delete Event"
          data-state="open"
          style="pointer-events: auto"
          @click.stop
        >
          <!-- Header -->
          <div class="bg-surface-elevation-2 px-4 pb-6 pt-5 sm:px-6">
            <div class="flex">
              <div class="w-full flex-1">
                <div class="mb-6 flex items-center justify-between">
                  <div class="flex items-center space-x-2">
                    <h3 class="text-3xl-semibold leading-6 text-ink-gray-9">
                      {{ __('Delete') }}
                    </h3>
                  </div>
                  <Button variant="ghost" @click="cancelDelete">
                    <template #icon>
                      <FeatherIcon name="x" class="h-4 w-4 text-ink-gray-9" />
                    </template>
                  </Button>
                </div>
                <p class="text-p-base text-ink-gray-7">
                  {{ __('Are you sure you want to delete this event?') }}
                </p>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="px-4 pb-7 pt-4 sm:px-6">
            <div class="space-y-2">
              <Button
                :label="__('Delete')"
                class="w-full"
                variant="solid"
                theme="red"
                :loading="saving"
                @click="confirmDelete"
              />
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import EventNotifications from './EventNotifications.vue'
import Attendee from './Attendee.vue'
import {
  Switch,
  TextEditor,
  ErrorMessage,
  DatePicker,
  TimePicker,
  dayjs,
  Dropdown,
  TextInput,
  FormControl,
  FeatherIcon,
  Button,
} from 'frappe-ui'
import { validateEmail } from '../utils'
import {
  normalizeParticipants,
  buildEndTimeOptions,
  computeAutoToTime,
  validateTimeRange,
} from '../composables/event'
import { onMounted, ref, computed, h } from 'vue'

// CalendarColorMap is not exported from frappe-ui's public index — define inline
const colorMap = {
  green: { color: '#30A66D' },
  amber: { color: '#DB7706' },
  violet: { color: '#6846E3' },
  pink: { color: '#E34AA6' },
  cyan: { color: '#2BA8AB' },
  blue: { color: '#3278E4' },
  orange: { color: '#E85F2C' },
}

const __ =
  window.__ ||
  ((s, r) => (r ? s.replace(/\{(\d+)\}/g, (_, i) => r[i] ?? _) : s))

const props = defineProps({
  event: { type: Object, default: () => ({}) },
  doctype: { type: String, default: '' },
  docname: { type: String, default: '' },
})

const emit = defineEmits(['close', 'saved', 'deleted'])

const titleRef = ref(null)
const saving = ref(false)
const error = ref(null)
const showDeleteDialog = ref(false)

const mode = computed(() =>
  _event.value.id === 'duplicate'
    ? 'duplicate'
    : _event.value.id
      ? 'edit'
      : 'create',
)

const oldEvent = ref({})
const _event = ref({
  title: '',
  description: '',
  fromDate: '',
  toDate: '',
  fromTime: '',
  toTime: '',
  isFullDay: false,
  eventType: 'Public',
  location: '',
  color: '#30A66D',
  referenceDoctype: '',
  referenceDocname: '',
  event_participants: [],
  notifications: [],
})

const dirty = computed(
  () => JSON.stringify(_event.value) !== JSON.stringify(oldEvent.value),
)

const peoples = computed({
  get() {
    return _event.value.event_participants || []
  },
  set(list) {
    _event.value.event_participants = normalizeParticipants(list)
  },
})

const toOptions = computed(() => buildEndTimeOptions(_event.value.fromTime))

const colors = Object.keys(colorMap).map((c) => ({
  label: c.charAt(0).toUpperCase() + c.slice(1),
  value: colorMap[c].color,
  icon: h('div', {
    class: '!size-2.5 rounded-full',
    style: { backgroundColor: colorMap[c].color },
  }),
  onClick: () => (_event.value.color = colorMap[c].color),
}))

onMounted(() => {
  if (props.event) {
    let start = dayjs(props.event.starts_on)
    let end = dayjs(props.event.ends_on)
    if (!props.event.name) {
      start = dayjs()
      end = dayjs().add(1, 'hour')
    }
    _event.value = {
      id: props.event.name || '',
      title: props.event.subject || '',
      description: props.event.description || '',
      fromDate: start.format('YYYY-MM-DD'),
      toDate: end.format('YYYY-MM-DD'),
      fromTime: start.format('HH:mm'),
      toTime: end.format('HH:mm'),
      isFullDay: !!props.event.all_day,
      eventType: props.event.event_type || 'Public',
      location: props.event.location || '',
      color: props.event.color || '#30A66D',
      referenceDoctype: props.event.reference_doctype || '',
      referenceDocname: props.event.reference_docname || '',
      event_participants: props.event.event_participants || [],
      notifications: props.event.notifications || [],
    }
    oldEvent.value = JSON.parse(JSON.stringify(_event.value))
    setTimeout(() => titleRef.value?.el?.focus(), 100)
  }
})

function updateDate(d) {
  _event.value.fromDate = d
  _event.value.toDate = d
}

function updateTime(t, fromTime = false) {
  error.value = null
  const prevTo = _event.value.toTime
  if (fromTime) {
    _event.value.fromTime = t
    if (!_event.value.toTime || _event.value.toTime <= t) {
      _event.value.toTime = computeAutoToTime(t)
    }
  } else {
    _event.value.toTime = t
  }
  const { valid, error: err } = validateTimeRange({
    fromDate: _event.value.fromDate,
    fromTime: _event.value.fromTime,
    toTime: _event.value.toTime,
    isFullDay: _event.value.isFullDay,
  })
  if (!valid) {
    error.value = err
    _event.value.toTime = prevTo
  }
}

function update() {
  error.value = null
  if (!_event.value.title) {
    error.value = __('Title is required')
    titleRef.value?.el?.focus()
    return
  }
  const { valid, error: err } = validateTimeRange({
    fromDate: _event.value.fromDate,
    fromTime: _event.value.fromTime,
    toTime: _event.value.toTime,
    isFullDay: _event.value.isFullDay,
  })
  if (!valid) {
    error.value = err
    return
  }

  if (_event.value.id && _event.value.id !== 'duplicate') {
    updateEvent()
  } else {
    createEvent()
  }
}

function createEvent() {
  saving.value = true
  error.value = null
  apiFetch('frappe.client.insert', {
    doc: {
      doctype: 'Event',
      subject: _event.value.title,
      description: _event.value.description,
      starts_on: _event.value.fromDate + ' ' + _event.value.fromTime,
      ends_on: _event.value.toDate + ' ' + _event.value.toTime,
      all_day: _event.value.isFullDay || false,
      event_type: _event.value.eventType,
      location: _event.value.location || '',
      color: _event.value.color,
      reference_doctype: props.doctype,
      reference_docname: props.docname,
      event_participants: _event.value.event_participants,
      notifications: _event.value.notifications,
    },
  })
    .then(() => emit('saved'))
    .catch((e) => {
      error.value = e?.message || __('Failed to create event')
    })
    .finally(() => {
      saving.value = false
    })
}

function updateEvent() {
  if (!_event.value.id) {
    error.value = __('Event ID is required')
    return
  }
  saving.value = true
  error.value = null
  apiFetch('frappe.client.set_value', {
    doctype: 'Event',
    name: _event.value.id,
    fieldname: {
      subject: _event.value.title,
      description: _event.value.description,
      starts_on: _event.value.fromDate + ' ' + _event.value.fromTime,
      ends_on: _event.value.toDate + ' ' + _event.value.toTime,
      all_day: _event.value.isFullDay,
      event_type: _event.value.eventType,
      location: _event.value.location || '',
      color: _event.value.color,
      reference_doctype: props.doctype,
      reference_docname: props.docname,
      event_participants: _event.value.event_participants,
      notifications: _event.value.notifications,
    },
  })
    .then(() => emit('saved'))
    .catch((e) => {
      error.value = e?.message || __('Failed to update event')
    })
    .finally(() => {
      saving.value = false
    })
}

function duplicateEvent() {
  if (!_event.value.id) return
  _event.value.id = 'duplicate'
  _event.value.title = _event.value.title + ' (Copy)'
  setTimeout(() => titleRef.value?.el?.focus(), 100)
}

function deleteEvent() {
  if (!_event.value.id) return
  showDeleteDialog.value = true
}

function confirmDelete() {
  if (!_event.value.id) return
  showDeleteDialog.value = false
  saving.value = true
  apiFetch('frappe.client.delete', { doctype: 'Event', name: _event.value.id })
    .then(() => {
      emit('deleted')
    })
    .catch((e) => {
      error.value = e?.message || 'Failed to delete event'
    })
    .finally(() => {
      saving.value = false
    })
}

function cancelDelete() {
  showDeleteDialog.value = false
}

function csrf() {
  return (
    window.frappe?.csrf_token ||
    window.csrf_token ||
    window.boot?.csrf_token ||
    ''
  )
}

async function apiFetch(method, params = {}) {
  const res = await fetch(`/api/method/${method}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-Frappe-CSRF-Token': csrf(),
      Accept: 'application/json',
    },
    body: JSON.stringify(params),
  })
  const data = await res.json()
  if (!res.ok || data.exc) {
    let msg = data.exc || ''
    try {
      const msgs = JSON.parse(data._server_messages || '[]')
      const parsed = msgs.map((m) => {
        try {
          return JSON.parse(m).message
        } catch {
          return m
        }
      })
      if (parsed.length) msg = parsed.join('\n')
    } catch {
      // ignore JSON parse errors on the outer _server_messages wrapper
    }
    throw new Error(msg || `HTTP ${res.status}`)
  }
  return data.message
}
</script>

<style scoped>
/*
 * Fix: in this build, Tailwind's logical-property classes (`end-0`, `pe-2`) on the
 * DatePicker/TimePicker suffix-icon container don't get compiled into the bundle,
 * so the absolutely-positioned chevron wrapper falls back to its in-flow location
 * (the LEFT edge of the input) instead of the right edge.
 *
 * We narrowly target the suffix-wrapper inside frappe-ui's Date/Time pickers
 * within this row only — `:deep()` pierces the scoped boundary, and the
 * `.fcrm-xt-datetime-row` class limits the rule to this component.
 */
.fcrm-xt-datetime-row :deep(.relative > .absolute.end-0) {
  right: 0;
  left: auto;
  inset-inline-end: 0;
  inset-inline-start: auto;
  padding-inline-end: 0.5rem; /* matches pe-2 (8px) */
}

/* Stretch the Visibility select trigger to the full field width. */
.fcrm-xt-visibility-select :deep(button[role='combobox'][data-slot='trigger']) {
  width: 100%;
  justify-content: space-between;
}
</style>
