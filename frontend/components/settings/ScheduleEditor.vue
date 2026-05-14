<template>
  <div class="border-t border-gray-100 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-800/60 px-4 py-4 space-y-4">
    <!-- Preset grid -->
    <div>
      <p class="eyebrow mb-2">Frequency</p>
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="preset in PRESETS"
          :key="preset.value"
          type="button"
          @click="selectPreset(preset.value)"
          class="px-3 py-1 text-xs rounded-full border transition-colors"
          :class="selectedPreset === preset.value
            ? 'bg-blue-600 border-blue-600 text-white'
            : 'border-gray-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-gray-600 dark:text-neutral-300 hover:border-blue-300 hover:text-blue-600 dark:hover:border-blue-500 dark:hover:text-blue-400'"
        >
          {{ preset.label }}
        </button>
        <button
          type="button"
          @click="selectPreset(null)"
          class="px-3 py-1 text-xs rounded-full border transition-colors"
          :class="selectedPreset === null
            ? 'bg-blue-600 border-blue-600 text-white'
            : 'border-gray-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-gray-600 dark:text-neutral-300 hover:border-blue-300 hover:text-blue-600 dark:hover:border-blue-500 dark:hover:text-blue-400'"
        >
          Custom
        </button>
      </div>
    </div>

    <!-- Day-of-week toggle bank (weekly preset + custom cron mode) -->
    <div v-if="showDayPicker">
      <p class="eyebrow mb-2">Days</p>
      <div class="flex gap-1">
        <button
          v-for="day in DAYS"
          :key="day.value"
          type="button"
          @click="toggleDay(day.value)"
          class="h-8 w-8 rounded-full text-xs font-medium transition-colors border"
          :class="selectedDays.has(day.value)
            ? 'bg-blue-600 border-blue-600 text-white'
            : 'border-gray-200 dark:border-neutral-600 bg-white dark:bg-neutral-700 text-gray-600 dark:text-neutral-300 hover:border-blue-300 hover:text-blue-600'"
        >
          {{ day.label }}
        </button>
      </div>
    </div>

    <!-- Time picker for daily / weekly / weekdays / custom-with-time -->
    <div v-if="showTimePicker">
      <p class="eyebrow mb-2">Time (UTC)</p>
      <div class="flex items-center gap-2">
        <select
          v-model="hour"
          class="rounded-lg border border-gray-300 dark:border-neutral-600 dark:bg-neutral-700 dark:text-white px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option v-for="h in 24" :key="h - 1" :value="h - 1">{{ String(h - 1).padStart(2, '0') }}</option>
        </select>
        <span class="text-gray-400 dark:text-neutral-500 font-medium">:</span>
        <select
          v-model="minute"
          class="rounded-lg border border-gray-300 dark:border-neutral-600 dark:bg-neutral-700 dark:text-white px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option :value="0">00</option>
          <option :value="15">15</option>
          <option :value="30">30</option>
          <option :value="45">45</option>
        </select>
        <span class="text-xs text-gray-400 dark:text-neutral-500">{{ browserTz }}</span>
      </div>
    </div>

    <!-- Custom cron input (no day bank) -->
    <div v-if="selectedPreset === null">
      <p class="eyebrow mb-2">Cron expression</p>
      <input
        v-model="cronInput"
        type="text"
        placeholder="e.g. 0 9 * * 1-5"
        class="w-full rounded-lg border border-gray-300 dark:border-neutral-600 dark:bg-neutral-700 dark:text-white px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      <p class="text-xs text-gray-400 dark:text-neutral-500 mt-1">Standard 5-field cron: minute hour day month weekday</p>
    </div>

    <!-- Actions -->
    <div class="flex items-center gap-2">
      <UiButton size="sm" :loading="saving" @click="handleSave">Save</UiButton>
      <UiButton size="sm" variant="outline" @click="$emit('cancel')">Cancel</UiButton>
    </div>
  </div>
</template>

<script setup lang="ts">
const TIME_BASED_PRESETS = ['daily', 'weekly', 'weekdays']

const PRESETS = [
  { label: '5m', value: '5m' },
  { label: '15m', value: '15m' },
  { label: '30m', value: '30m' },
  { label: '1h', value: '1h' },
  { label: '2h', value: '2h' },
  { label: '6h', value: '6h' },
  { label: '12h', value: '12h' },
  { label: 'Daily', value: 'daily' },
  { label: 'Weekly', value: 'weekly' },
  { label: 'Weekdays', value: 'weekdays' },
]

const DAYS = [
  { label: 'S', value: 0 },
  { label: 'M', value: 1 },
  { label: 'T', value: 2 },
  { label: 'W', value: 3 },
  { label: 'T', value: 4 },
  { label: 'F', value: 5 },
  { label: 'S', value: 6 },
]

const CRON_PATTERNS: Record<string, RegExp> = {
  daily: /^(\d+) (\d+) \* \* \*$/,
  weekly: /^(\d+) (\d+) \* \* (\d+)$/,
  weekdays: /^(\d+) (\d+) \* \* 1-5$/,
}

const props = defineProps<{
  scheduleType: 'preset' | 'cron'
  scheduleValue: string
  saving: boolean
}>()

const emit = defineEmits<{
  save: [scheduleType: string, scheduleValue: string, timezone: string]
  cancel: []
}>()

const selectedPreset = ref<string | null>(null)
const cronInput = ref('')
const hour = ref(9)
const minute = ref(0)
const selectedDays = ref<Set<number>>(new Set([1]))

const showTimePicker = computed(() =>
  selectedPreset.value !== null && TIME_BASED_PRESETS.includes(selectedPreset.value)
)

const showDayPicker = computed(() =>
  selectedPreset.value === 'weekly'
)

onMounted(() => {
  if (props.scheduleType === 'preset') {
    selectedPreset.value = props.scheduleValue
    if (props.scheduleValue === 'weekdays') {
      selectedDays.value = new Set([1, 2, 3, 4, 5])
    }
  } else {
    // Try to detect if the cron matches a known pattern
    let matched = false
    for (const [presetKey, pattern] of Object.entries(CRON_PATTERNS)) {
      const m = props.scheduleValue.match(pattern)
      if (m) {
        selectedPreset.value = presetKey
        minute.value = parseInt(m[1])
        hour.value = parseInt(m[2])
        if (presetKey === 'weekly') {
          selectedDays.value = new Set([parseInt(m[3])])
        } else if (presetKey === 'weekdays') {
          selectedDays.value = new Set([1, 2, 3, 4, 5])
        }
        matched = true
        break
      }
    }
    if (!matched) {
      selectedPreset.value = null
      cronInput.value = props.scheduleValue
    }
  }
})

function selectPreset(value: string | null) {
  selectedPreset.value = value
  if (value === 'weekdays') {
    selectedDays.value = new Set([1, 2, 3, 4, 5])
  } else if (value === 'weekly' && selectedDays.value.size === 0) {
    selectedDays.value = new Set([1])
  }
}

function toggleDay(dayNum: number) {
  const next = new Set(selectedDays.value)
  if (next.has(dayNum)) {
    if (next.size > 1) next.delete(dayNum) // keep at least 1 day
  } else {
    next.add(dayNum)
  }
  selectedDays.value = next
}

function handleSave() {
  if (selectedPreset.value === null) {
    if (!cronInput.value.trim()) return
    emit('save', 'cron', cronInput.value.trim(), browserTz)
    return
  }

  if (TIME_BASED_PRESETS.includes(selectedPreset.value)) {
    if (selectedPreset.value === 'daily') {
      emit('save', 'cron', `${minute.value} ${hour.value} * * *`)
    } else if (selectedPreset.value === 'weekdays') {
      emit('save', 'cron', `${minute.value} ${hour.value} * * 1-5`)
    } else if (selectedPreset.value === 'weekly') {
      const days = [...selectedDays.value].sort().join(',')
      emit('save', 'cron', `${minute.value} ${hour.value} * * ${days}`)
    }
  } else {
    emit('save', 'preset', selectedPreset.value, browserTz)
  }
}
</script>
