<template>
  <div class="border-t border-gray-100 bg-gray-50 px-4 py-4 space-y-4">
    <!-- Preset grid -->
    <div>
      <p class="text-xs font-medium text-gray-500 mb-2">Frequency</p>
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="preset in PRESETS"
          :key="preset.value"
          type="button"
          @click="selectPreset(preset.value)"
          class="px-3 py-1 text-xs rounded-full border transition-colors"
          :class="selectedPreset === preset.value
            ? 'bg-blue-600 border-blue-600 text-white'
            : 'border-gray-200 bg-white text-gray-600 hover:border-blue-300 hover:text-blue-600'"
        >
          {{ preset.label }}
        </button>
        <button
          type="button"
          @click="selectPreset(null)"
          class="px-3 py-1 text-xs rounded-full border transition-colors"
          :class="selectedPreset === null
            ? 'bg-blue-600 border-blue-600 text-white'
            : 'border-gray-200 bg-white text-gray-600 hover:border-blue-300 hover:text-blue-600'"
        >
          Custom
        </button>
      </div>
    </div>

    <!-- Time picker for daily/weekly/weekdays -->
    <div v-if="showTimePicker">
      <p class="text-xs font-medium text-gray-500 mb-2">Time (UTC)</p>
      <div class="flex items-center gap-2">
        <select
          v-model="hour"
          class="rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option v-for="h in 24" :key="h - 1" :value="h - 1">{{ String(h - 1).padStart(2, '0') }}</option>
        </select>
        <span class="text-gray-400 font-medium">:</span>
        <select
          v-model="minute"
          class="rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option :value="0">00</option>
          <option :value="15">15</option>
          <option :value="30">30</option>
          <option :value="45">45</option>
        </select>
        <span class="text-xs text-gray-400">UTC</span>
      </div>
    </div>

    <!-- Custom cron input -->
    <div v-if="selectedPreset === null">
      <p class="text-xs font-medium text-gray-500 mb-2">Cron expression</p>
      <input
        v-model="cronInput"
        type="text"
        placeholder="e.g. 0 9 * * 1-5"
        class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      <p class="text-xs text-gray-400 mt-1">Standard 5-field cron: minute hour day month weekday</p>
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

const CRON_PATTERNS: Record<string, RegExp> = {
  daily: /^(\d+) (\d+) \* \* \*$/,
  weekly: /^(\d+) (\d+) \* \* 1$/,
  weekdays: /^(\d+) (\d+) \* \* 1-5$/,
}

const props = defineProps<{
  scheduleType: 'preset' | 'cron'
  scheduleValue: string
  saving: boolean
}>()

const emit = defineEmits<{
  save: [scheduleType: string, scheduleValue: string]
  cancel: []
}>()

const selectedPreset = ref<string | null>(null)
const cronInput = ref('')
const hour = ref(9)
const minute = ref(0)

const showTimePicker = computed(() =>
  selectedPreset.value !== null && TIME_BASED_PRESETS.includes(selectedPreset.value)
)

onMounted(() => {
  if (props.scheduleType === 'preset') {
    selectedPreset.value = props.scheduleValue
  } else {
    // Try to detect if the cron matches a time-based pattern
    let matched = false
    for (const [presetKey, pattern] of Object.entries(CRON_PATTERNS)) {
      const m = props.scheduleValue.match(pattern)
      if (m) {
        selectedPreset.value = presetKey
        minute.value = parseInt(m[1])
        hour.value = parseInt(m[2])
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
}

function handleSave() {
  if (selectedPreset.value === null) {
    if (!cronInput.value.trim()) return
    emit('save', 'cron', cronInput.value.trim())
    return
  }

  if (TIME_BASED_PRESETS.includes(selectedPreset.value)) {
    const cronMap: Record<string, string> = {
      daily: `${minute.value} ${hour.value} * * *`,
      weekly: `${minute.value} ${hour.value} * * 1`,
      weekdays: `${minute.value} ${hour.value} * * 1-5`,
    }
    emit('save', 'cron', cronMap[selectedPreset.value])
  } else {
    emit('save', 'preset', selectedPreset.value)
  }
}
</script>
