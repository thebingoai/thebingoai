<template>
  <div class="relative" ref="wrapperRef">
    <button
      @click="open = !open"
      class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm font-medium transition-colors"
      :class="[
        hasSchedule
          ? 'bg-violet-500/15 text-violet-400 hover:bg-violet-500/25'
          : 'bg-white/5 text-white/50 hover:bg-white/10 hover:text-white/80'
      ]"
      :title="hasSchedule ? `Refreshes ${currentLabel}` : 'Set refresh schedule'"
    >
      <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <polyline points="12 6 12 12 16 14"/>
      </svg>
      <span v-if="hasSchedule" class="text-xs">{{ currentLabel }}</span>
    </button>

    <!-- Popover -->
    <Transition name="popover">
      <div
        v-if="open"
        class="absolute right-0 top-full mt-2 w-72 bg-zinc-900 border border-white/10 rounded-xl shadow-2xl z-50 p-4 space-y-4"
      >
        <div class="flex items-center justify-between">
          <span class="text-sm font-medium text-white">Refresh Schedule</span>
          <button @click="open = false" class="text-white/40 hover:text-white/70 transition-colors">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <!-- Current status -->
        <div v-if="hasSchedule" class="bg-white/5 rounded-lg p-3 space-y-1.5">
          <div class="flex items-center justify-between">
            <span class="text-xs text-white/50">Schedule</span>
            <span class="text-xs font-medium text-violet-400">{{ currentLabel }}</span>
          </div>
          <div v-if="dashboard?.next_run_at" class="flex items-center justify-between">
            <span class="text-xs text-white/50">Next refresh</span>
            <span class="text-xs text-white/70">{{ formatRelative(dashboard.next_run_at) }}</span>
          </div>
          <div v-if="dashboard?.last_run_at" class="flex items-center justify-between">
            <span class="text-xs text-white/50">Last refresh</span>
            <span class="text-xs text-white/70">{{ formatRelative(dashboard.last_run_at) }}</span>
          </div>
          <!-- Active toggle -->
          <div class="flex items-center justify-between pt-1">
            <span class="text-xs text-white/50">Active</span>
            <button
              @click="handleToggle"
              :disabled="toggling"
              class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none"
              :class="dashboard?.schedule_active ? 'bg-violet-500' : 'bg-white/10'"
            >
              <span
                class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
                :class="dashboard?.schedule_active ? 'translate-x-4.5' : 'translate-x-0.5'"
              />
            </button>
          </div>
        </div>

        <!-- Preset selector -->
        <div class="space-y-2">
          <label class="text-xs text-white/50">Refresh every</label>
          <div class="grid grid-cols-4 gap-1.5">
            <button
              v-for="preset in PRESETS"
              :key="preset.value"
              @click="selectPreset(preset.value)"
              class="px-2 py-1.5 rounded-lg text-xs font-medium transition-colors"
              :class="[
                selectedPreset === preset.value && scheduleMode === 'preset'
                  ? 'bg-violet-500 text-white'
                  : 'bg-white/5 text-white/60 hover:bg-white/10 hover:text-white'
              ]"
            >
              {{ preset.label }}
            </button>
          </div>
        </div>

        <!-- Custom cron -->
        <div class="space-y-1.5">
          <label class="text-xs text-white/50">Custom cron expression</label>
          <div class="flex gap-2">
            <input
              v-model="customCron"
              @focus="scheduleMode = 'cron'"
              placeholder="*/30 * * * *"
              class="flex-1 px-2.5 py-1.5 bg-white/5 border border-white/10 rounded-lg text-xs text-white placeholder-white/30 focus:outline-none focus:border-violet-500/50"
            />
          </div>
          <p v-if="cronError" class="text-xs text-red-400">{{ cronError }}</p>
        </div>

        <!-- Action buttons -->
        <div class="flex gap-2 pt-1">
          <button
            @click="handleSave"
            :disabled="saving || (!selectedPreset && !customCron)"
            class="flex-1 py-2 rounded-lg text-xs font-medium bg-violet-500 text-white hover:bg-violet-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {{ saving ? 'Saving…' : (hasSchedule ? 'Update' : 'Enable') }}
          </button>
          <button
            @click="handleTrigger"
            :disabled="triggering"
            class="px-3 py-2 rounded-lg text-xs font-medium bg-white/5 text-white/70 hover:bg-white/10 disabled:opacity-40 transition-colors"
            title="Run now"
          >
            <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
          </button>
          <button
            v-if="hasSchedule"
            @click="handleRemove"
            :disabled="removing"
            class="px-3 py-2 rounded-lg text-xs font-medium bg-white/5 text-red-400/70 hover:bg-red-500/10 hover:text-red-400 disabled:opacity-40 transition-colors"
            title="Remove schedule"
          >
            <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
            </svg>
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useDashboardStore } from '~/stores/dashboard'
import { useApi } from '~/composables/useApi'

const props = defineProps<{ dashboardId: number }>()

const dashboardStore = useDashboardStore()
const api = useApi()

const open = ref(false)
const scheduleMode = ref<'preset' | 'cron'>('preset')
const selectedPreset = ref<string>('')
const customCron = ref('')
const cronError = ref('')
const saving = ref(false)
const toggling = ref(false)
const removing = ref(false)
const triggering = ref(false)
const wrapperRef = ref<HTMLElement | null>(null)

const PRESETS = [
  { label: '15m', value: '15m' },
  { label: '30m', value: '30m' },
  { label: '1h',  value: '1h' },
  { label: '2h',  value: '2h' },
  { label: '6h',  value: '6h' },
  { label: '12h', value: '12h' },
  { label: 'Daily', value: 'daily' },
  { label: 'Weekly', value: 'weekly' },
]

const dashboard = computed(() => dashboardStore.dashboards.find(d => d.id === props.dashboardId))
const hasSchedule = computed(() => !!dashboard.value?.cron_expression)

const currentLabel = computed(() => {
  const d = dashboard.value
  if (!d?.schedule_type) return ''
  if (d.schedule_type === 'preset') return d.schedule_value ?? ''
  return d.cron_expression ?? ''
})

function selectPreset(value: string) {
  selectedPreset.value = value
  scheduleMode.value = 'preset'
  customCron.value = ''
  cronError.value = ''
}

function formatRelative(isoStr: string): string {
  const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000)
  if (diff < 0) {
    const future = Math.abs(diff)
    if (future < 60) return `in ${future}s`
    if (future < 3600) return `in ${Math.floor(future / 60)}m`
    return `in ${Math.floor(future / 3600)}h`
  }
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

async function handleSave() {
  cronError.value = ''
  const isPreset = scheduleMode.value === 'preset' && selectedPreset.value
  const isCron = scheduleMode.value === 'cron' && customCron.value

  if (!isPreset && !isCron) return

  saving.value = true
  try {
    await dashboardStore.setSchedule(
      props.dashboardId,
      isPreset ? 'preset' : 'cron',
      isPreset ? selectedPreset.value : customCron.value
    )
    open.value = false
  } catch (err: any) {
    cronError.value = err?.data?.detail ?? 'Invalid schedule'
  } finally {
    saving.value = false
  }
}

async function handleToggle() {
  if (!dashboard.value) return
  toggling.value = true
  try {
    await dashboardStore.toggleSchedule(props.dashboardId, !dashboard.value.schedule_active)
  } finally {
    toggling.value = false
  }
}

async function handleRemove() {
  removing.value = true
  try {
    await dashboardStore.removeSchedule(props.dashboardId)
    selectedPreset.value = ''
    customCron.value = ''
    open.value = false
  } finally {
    removing.value = false
  }
}

async function handleTrigger() {
  triggering.value = true
  try {
    await api.dashboards.triggerRefresh(props.dashboardId)
  } finally {
    triggering.value = false
  }
}

// Close on outside click
function onDocumentClick(e: MouseEvent) {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target as Node)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', onDocumentClick, true))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick, true))
</script>

<style scoped>
.popover-enter-active,
.popover-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}
.popover-enter-from,
.popover-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.97);
}
</style>
