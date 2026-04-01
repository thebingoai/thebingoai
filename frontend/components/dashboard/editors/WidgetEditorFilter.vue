<template>
  <div class="h-full overflow-y-auto p-5 space-y-5">

    <!-- Controls header -->
    <div class="flex items-center justify-between">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Filter Controls</h3>
      <button
        v-if="editMode"
        class="flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
        @click="addControl()"
      >
        <span class="text-base leading-none">+</span> Add Control
      </button>
    </div>

    <!-- Controls list -->
    <div class="space-y-3">
      <div
        v-for="(control, i) in localControls"
        :key="i"
        class="rounded-lg border border-gray-200 p-3 space-y-2 bg-gray-50"
      >
        <!-- Row 1: Type + Label -->
        <div class="flex gap-2">
          <div class="w-1/3 space-y-1">
            <label class="text-[10px] text-gray-400">Type</label>
            <select
              v-model="control.type"
              :disabled="!editMode"
              class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
              @change="onTypeChange(control); emitUpdate()"
            >
              <option value="dropdown">Dropdown</option>
              <option value="search">Search</option>
              <option value="date_range">Date Range</option>
            </select>
          </div>
          <div class="flex-1 space-y-1">
            <label class="text-[10px] text-gray-400">Label</label>
            <input
              v-model="control.label"
              type="text"
              placeholder="Filter label"
              class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
              :readonly="!editMode"
              :class="!editMode ? 'cursor-default bg-gray-50' : ''"
              @input="emitUpdate()"
            />
          </div>
        </div>

        <!-- Row 2: Key + Column -->
        <div class="flex gap-2">
          <div class="flex-1 space-y-1">
            <label class="text-[10px] text-gray-400">Key</label>
            <input
              v-model="control.key"
              type="text"
              placeholder="unique_key"
              class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
              :readonly="!editMode"
              :class="!editMode ? 'cursor-default bg-gray-50' : ''"
              @input="emitUpdate()"
            />
          </div>
          <div class="flex-1 space-y-1">
            <label class="text-[10px] text-gray-400">DB Column</label>
            <input
              v-model="control.column"
              type="text"
              placeholder="column_name"
              class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
              :readonly="!editMode"
              :class="!editMode ? 'cursor-default bg-gray-50' : ''"
              @input="emitUpdate()"
            />
          </div>
        </div>

        <!-- Row 3: Dropdown-specific options -->
        <template v-if="control.type === 'dropdown'">
          <!-- Multi-select toggle -->
          <div class="flex items-center gap-1.5">
            <span class="text-xs text-gray-600">Allow multiple</span>
            <button
              type="button"
              role="switch"
              :aria-checked="!!control.multiple"
              :disabled="!editMode"
              class="relative inline-flex h-4 w-7 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="control.multiple ? 'bg-indigo-600' : 'bg-gray-200'"
              @click="editMode && (control.multiple = !control.multiple, emitUpdate())"
            >
              <span
                class="pointer-events-none inline-block h-3 w-3 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
                :class="control.multiple ? 'translate-x-3 ml-0.5' : 'translate-x-0 ml-0.5'"
              />
            </button>
          </div>

          <!-- Options source toggle -->
          <div class="flex items-center gap-2">
            <button
              v-for="mode in (['static', 'dynamic'] as const)"
              :key="mode"
              :disabled="!editMode"
              class="rounded px-2 py-0.5 text-[10px] font-medium transition-colors disabled:opacity-60"
              :class="getOptionsMode(control) === mode
                ? 'bg-indigo-100 text-indigo-700'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'"
              @click="editMode && setOptionsMode(control, mode)"
            >
              {{ mode === 'static' ? 'Static Options' : 'Dynamic SQL' }}
            </button>
          </div>

          <!-- Static options -->
          <div v-if="getOptionsMode(control) === 'static'" class="space-y-1">
            <label class="text-[10px] text-gray-400">Options (comma-separated)</label>
            <input
              :value="(control.options ?? []).join(', ')"
              type="text"
              placeholder="Option A, Option B, Option C"
              class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
              :readonly="!editMode"
              :class="!editMode ? 'cursor-default bg-gray-50' : ''"
              @input="onStaticOptionsInput(control, ($event.target as HTMLInputElement).value)"
            />
          </div>

          <!-- Dynamic SQL options -->
          <div v-else class="space-y-2">
            <div class="space-y-1">
              <label class="text-[10px] text-gray-400">Connection</label>
              <select
                :value="control.optionsSource?.connectionId ?? ''"
                :disabled="!editMode"
                class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
                @change="onDynamicConnectionChange(control, Number(($event.target as HTMLSelectElement).value))"
              >
                <option value="" disabled>Select connection…</option>
                <option v-for="conn in connections" :key="conn.id" :value="conn.id">
                  {{ conn.name }}
                </option>
              </select>
            </div>
            <div class="space-y-1">
              <label class="text-[10px] text-gray-400">SQL Query</label>
              <textarea
                :value="control.optionsSource?.sql ?? ''"
                rows="2"
                placeholder="SELECT DISTINCT col AS option_value FROM table LIMIT 50"
                class="w-full rounded border border-gray-200 bg-white px-2 py-1 font-mono text-xs text-gray-800 leading-relaxed resize-none focus:outline-none focus:ring-1 focus:ring-indigo-300"
                :readonly="!editMode"
                :class="!editMode ? 'cursor-default bg-gray-50' : ''"
                spellcheck="false"
                @input="onDynamicSqlInput(control, ($event.target as HTMLTextAreaElement).value)"
              />
            </div>
          </div>
        </template>

        <!-- Row 3: Date range source (date_range only) -->
        <template v-if="control.type === 'date_range'">
          <div class="space-y-2">
            <div class="flex items-center gap-2">
              <span class="text-[10px] text-gray-400 font-medium uppercase tracking-wide">Date Range Source</span>
              <button
                v-if="editMode"
                type="button"
                class="rounded px-2 py-0.5 text-[10px] font-medium transition-colors"
                :class="control.dateRangeSource
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'bg-gray-100 text-gray-500 hover:bg-gray-200'"
                @click="toggleDateRangeSource(control)"
              >
                {{ control.dateRangeSource ? 'Enabled' : 'Enable' }}
              </button>
            </div>
            <template v-if="control.dateRangeSource">
              <div class="space-y-1">
                <label class="text-[10px] text-gray-400">Connection</label>
                <select
                  :value="control.dateRangeSource?.connectionId ?? ''"
                  :disabled="!editMode"
                  class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
                  @change="onDateRangeConnectionChange(control, Number(($event.target as HTMLSelectElement).value))"
                >
                  <option value="" disabled>Select connection…</option>
                  <option v-for="conn in connections" :key="conn.id" :value="conn.id">
                    {{ conn.name }}
                  </option>
                </select>
              </div>
              <div class="space-y-1">
                <label class="text-[10px] text-gray-400">SQL Query (must return min_date and max_date)</label>
                <textarea
                  :value="control.dateRangeSource?.sql ?? ''"
                  rows="2"
                  placeholder="SELECT MIN(t.date_col) AS min_date, MAX(t.date_col) AS max_date FROM table t"
                  class="w-full rounded border border-gray-200 bg-white px-2 py-1 font-mono text-xs text-gray-800 leading-relaxed resize-none focus:outline-none focus:ring-1 focus:ring-indigo-300"
                  :readonly="!editMode"
                  :class="!editMode ? 'cursor-default bg-gray-50' : ''"
                  spellcheck="false"
                  @input="onDateRangeSqlInput(control, ($event.target as HTMLTextAreaElement).value)"
                />
              </div>
            </template>
          </div>
        </template>

        <!-- Remove button -->
        <div v-if="editMode" class="flex justify-end">
          <button
            class="flex items-center gap-1 text-[10px] text-gray-400 hover:text-rose-500 transition-colors"
            @click="removeControl(i)"
          >
            <X class="h-3 w-3" />
            Remove
          </button>
        </div>
      </div>

      <p v-if="localControls.length === 0" class="text-xs text-gray-400 text-center py-4">
        No filter controls. Add one to get started.
      </p>
    </div>

    <!-- Help note -->
    <p class="text-[11px] text-gray-400 bg-gray-100 rounded-lg px-3 py-2">
      Filter controls affect all SQL-backed widgets in this dashboard.
      Set the DB Column to match the column used in your widget queries.
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { X } from 'lucide-vue-next'
import type { WidgetConfig, FilterWidgetConfig, FilterControl } from '~/types/dashboard'
import { useApi } from '~/composables/useApi'

const props = defineProps<{
  modelValue: WidgetConfig
  editMode: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WidgetConfig]
}>()

const api = useApi()
const connections = ref<{ id: number; name: string }[]>([])

const filterConfig = computed(() => props.modelValue.config as FilterWidgetConfig)
const localControls = ref<FilterControl[]>(
  JSON.parse(JSON.stringify(filterConfig.value.controls)),
)

// Resync local state when the parent switches to a different widget
watch(() => props.modelValue, () => {
  localControls.value = JSON.parse(JSON.stringify(filterConfig.value.controls))
})

function emitUpdate() {
  emit('update:modelValue', {
    type: 'filter',
    config: {
      controls: localControls.value,
    },
  })
}

function addControl() {
  const idx = localControls.value.length
  localControls.value.push({
    type: 'dropdown',
    label: '',
    key: `filter_${idx}`,
    column: '',
    options: [],
  })
  emitUpdate()
}

function removeControl(i: number) {
  localControls.value.splice(i, 1)
  emitUpdate()
}

function onTypeChange(control: FilterControl) {
  // Clean up type-specific fields when switching
  if (control.type !== 'dropdown') {
    delete control.options
    delete control.optionsSource
    delete (control as any).multiple
  }
  if (control.type !== 'date_range') {
    delete control.dateRangeSource
  }
}

function getOptionsMode(control: FilterControl): 'static' | 'dynamic' {
  return control.optionsSource ? 'dynamic' : 'static'
}

function setOptionsMode(control: FilterControl, mode: 'static' | 'dynamic') {
  if (mode === 'static') {
    delete control.optionsSource
    if (!control.options) control.options = []
  } else {
    control.optionsSource = { connectionId: 0, sql: '' }
    delete control.options
  }
  emitUpdate()
}

function onStaticOptionsInput(control: FilterControl, value: string) {
  control.options = value.split(',').map(s => s.trim()).filter(Boolean)
  emitUpdate()
}

function onDynamicConnectionChange(control: FilterControl, connId: number) {
  if (!control.optionsSource) {
    control.optionsSource = { connectionId: connId, sql: '' }
  } else {
    control.optionsSource.connectionId = connId
  }
  emitUpdate()
}

function onDynamicSqlInput(control: FilterControl, sql: string) {
  if (!control.optionsSource) {
    control.optionsSource = { connectionId: 0, sql }
  } else {
    control.optionsSource.sql = sql
  }
  emitUpdate()
}

function toggleDateRangeSource(control: FilterControl) {
  if (control.dateRangeSource) {
    delete control.dateRangeSource
  } else {
    control.dateRangeSource = { connectionId: 0, sql: '' }
  }
  emitUpdate()
}

function onDateRangeConnectionChange(control: FilterControl, connId: number) {
  if (!control.dateRangeSource) {
    control.dateRangeSource = { connectionId: connId, sql: '' }
  } else {
    control.dateRangeSource.connectionId = connId
  }
  emitUpdate()
}

function onDateRangeSqlInput(control: FilterControl, sql: string) {
  if (!control.dateRangeSource) {
    control.dateRangeSource = { connectionId: 0, sql }
  } else {
    control.dateRangeSource.sql = sql
  }
  emitUpdate()
}

onMounted(async () => {
  try {
    const data = await api.connections.list() as { id: number; name: string }[]
    connections.value = data
  } catch {
    // silently ignore
  }
})
</script>
