<template>
  <div class="p-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 class="text-2xl font-medium text-gray-900">Jobs</h2>
        <p class="text-sm text-gray-500 mt-1">Scheduled tasks that periodically wake the AI agent to perform work autonomously.</p>
      </div>
      <UiButton size="sm" @click="openCreateDialog">
        Create Job
      </UiButton>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-3">
      <UiSkeleton class="h-16 w-full rounded-lg" />
      <UiSkeleton class="h-16 w-full rounded-lg" />
      <UiSkeleton class="h-16 w-full rounded-lg" />
    </div>

    <!-- Empty State -->
    <UiEmptyState
      v-else-if="jobs.length === 0"
      title="No jobs yet"
      description="Create a scheduled job to have the AI agent run tasks automatically on a recurring schedule."
      :icon="Timer"
    />

    <!-- Job List -->
    <div v-else class="space-y-2">
      <div
        v-for="job in jobs"
        :key="job.id"
        class="flex items-center gap-3 rounded-lg border border-gray-200 px-4 py-3"
      >
        <!-- Active toggle -->
        <button
          type="button"
          :title="job.is_active ? 'Deactivate job' : 'Activate job'"
          @click="handleToggle(job)"
          class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors"
          :class="job.is_active ? 'bg-blue-600' : 'bg-gray-200'"
        >
          <span
            class="inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform"
            :class="job.is_active ? 'translate-x-4' : 'translate-x-0.5'"
          />
        </button>

        <!-- Job info -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <p class="text-sm font-medium text-gray-900 truncate">{{ job.name }}</p>
            <span class="shrink-0 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-mono">
              {{ job.cron_expression }}
            </span>
          </div>
          <p class="text-xs text-gray-400 mt-0.5">
            <span v-if="job.last_run_at">Last run: {{ formatRelative(job.last_run_at) }} · </span>
            <span v-if="job.next_run_at && job.is_active">Next: {{ formatRelative(job.next_run_at) }}</span>
            <span v-else-if="!job.is_active" class="text-gray-300">Inactive</span>
          </p>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-1 shrink-0">
          <button
            type="button"
            title="Edit job"
            @click="openEditDialog(job)"
            class="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
          >
            <component :is="Pencil" class="h-4 w-4" />
          </button>
          <button
            type="button"
            title="View run history"
            @click="openRunHistory(job)"
            class="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
          >
            <component :is="History" class="h-4 w-4" />
          </button>
          <button
            type="button"
            title="Trigger now"
            @click="handleTrigger(job)"
            class="rounded-lg p-1.5 text-gray-400 hover:bg-blue-50 hover:text-blue-600 transition-colors"
          >
            <component :is="Play" class="h-4 w-4" />
          </button>
          <button
            type="button"
            title="Delete job"
            @click="openDeleteDialog(job)"
            class="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors"
          >
            <component :is="Trash2" class="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>

    <!-- Create / Edit Dialog -->
    <UiDialog
      v-model:open="showFormDialog"
      :title="editingJob ? 'Edit Job' : 'Create Job'"
      size="lg"
    >
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input
            v-model="form.name"
            type="text"
            placeholder="e.g. Daily standup summary"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Schedule</label>
          <select
            v-model="scheduleSelection"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option v-for="opt in PRESET_OPTIONS" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
            <option value="__cron__">Custom cron expression…</option>
          </select>
          <input
            v-if="scheduleSelection === '__cron__'"
            v-model="form.schedule_value"
            type="text"
            placeholder="e.g. 0 9 * * 1-5"
            class="mt-2 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Prompt</label>
          <textarea
            v-model="form.prompt"
            rows="6"
            placeholder="What should the AI do when this job runs? e.g. Summarize any new tasks from my database and send me a brief report."
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
          />
        </div>
      </div>

      <template #footer>
        <UiButton variant="outline" @click="showFormDialog = false">Cancel</UiButton>
        <UiButton :loading="saving" @click="saveJob">
          {{ editingJob ? 'Save Changes' : 'Create Job' }}
        </UiButton>
      </template>
    </UiDialog>

    <!-- Run History Dialog -->
    <UiDialog
      v-model:open="showRunHistoryDialog"
      :title="`Run History — ${historyJob?.name}`"
      size="xl"
    >
      <div v-if="runsLoading" class="space-y-2">
        <UiSkeleton class="h-12 w-full rounded-lg" />
        <UiSkeleton class="h-12 w-full rounded-lg" />
      </div>

      <UiEmptyState
        v-else-if="runs.length === 0"
        title="No runs yet"
        description="This job hasn't been triggered yet."
        :icon="History"
      />

      <div v-else class="space-y-2">
        <div
          v-for="run in runs"
          :key="run.id"
          class="rounded-lg border border-gray-200 overflow-hidden"
        >
          <!-- Run header -->
          <div
            class="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors"
            @click="toggleRunExpand(run.id)"
          >
            <span
              class="text-xs font-medium px-2 py-0.5 rounded-full"
              :class="{
                'bg-green-100 text-green-700': run.status === 'completed',
                'bg-red-100 text-red-700': run.status === 'failed',
                'bg-blue-100 text-blue-700': run.status === 'running',
              }"
            >
              {{ run.status }}
            </span>
            <span class="text-sm text-gray-700 flex-1">{{ formatDate(run.started_at) }}</span>
            <span v-if="run.duration_ms" class="text-xs text-gray-400">{{ run.duration_ms }}ms</span>
            <component :is="ChevronDown" class="h-4 w-4 text-gray-400 transition-transform" :class="{ 'rotate-180': expandedRuns.has(run.id) }" />
          </div>

          <!-- Run details (expanded) -->
          <div v-if="expandedRuns.has(run.id)" class="border-t border-gray-100 px-4 py-3 space-y-3 bg-gray-50">
            <div v-if="run.response">
              <p class="text-xs font-medium text-gray-500 mb-1">Response</p>
              <p class="text-sm text-gray-700 whitespace-pre-wrap">{{ run.response }}</p>
            </div>
            <div v-if="run.error">
              <p class="text-xs font-medium text-red-500 mb-1">Error</p>
              <p class="text-sm text-red-600 whitespace-pre-wrap font-mono">{{ run.error }}</p>
            </div>
          </div>
        </div>

        <!-- Pagination -->
        <div v-if="runsTotalPages > 1" class="flex justify-center gap-2 pt-2">
          <UiButton
            size="sm"
            variant="outline"
            :disabled="runsPage === 0"
            @click="loadRuns(runsPage - 1)"
          >
            Previous
          </UiButton>
          <UiButton
            size="sm"
            variant="outline"
            :disabled="runsPage >= runsTotalPages - 1"
            @click="loadRuns(runsPage + 1)"
          >
            Next
          </UiButton>
        </div>
      </div>

      <template #footer>
        <UiButton variant="outline" @click="showRunHistoryDialog = false">Close</UiButton>
      </template>
    </UiDialog>

    <!-- Delete Confirmation Dialog -->
    <UiDialog v-model:open="showDeleteDialog" title="Delete Job" size="sm">
      <p class="text-sm text-gray-600">
        Are you sure you want to delete <strong>{{ deletingJob?.name }}</strong>?
        All run history will also be deleted. This action cannot be undone.
      </p>
      <template #footer>
        <UiButton variant="outline" @click="showDeleteDialog = false">Cancel</UiButton>
        <UiButton variant="danger" :loading="deleting" @click="confirmDelete">Delete</UiButton>
      </template>
    </UiDialog>
  </div>
</template>

<script setup lang="ts">
import { Timer, Pencil, History, Play, Trash2, ChevronDown } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { HeartbeatJob, HeartbeatJobRun, HeartbeatJobRunListResponse } from '~/types/heartbeat'
import { PRESET_OPTIONS } from '~/types/heartbeat'

const api = useApi()

// ── Data ──────────────────────────────────────────────────────────────────
const jobs = ref<HeartbeatJob[]>([])
const loading = ref(true)

// ── Create / Edit form ────────────────────────────────────────────────────
const showFormDialog = ref(false)
const editingJob = ref<HeartbeatJob | null>(null)
const saving = ref(false)
const scheduleSelection = ref<string>('1h')

const form = reactive({
  name: '',
  prompt: '',
  schedule_value: '',
})

// ── Run History ────────────────────────────────────────────────────────────
const showRunHistoryDialog = ref(false)
const historyJob = ref<HeartbeatJob | null>(null)
const runs = ref<HeartbeatJobRun[]>([])
const runsLoading = ref(false)
const runsPage = ref(0)
const runsTotal = ref(0)
const runsPageSize = 10
const expandedRuns = ref(new Set<string>())
const runsTotalPages = computed(() => Math.ceil(runsTotal.value / runsPageSize))

// ── Delete ─────────────────────────────────────────────────────────────────
const showDeleteDialog = ref(false)
const deletingJob = ref<HeartbeatJob | null>(null)
const deleting = ref(false)

// ── Lifecycle ──────────────────────────────────────────────────────────────
onMounted(fetchJobs)

// ── Fetch ──────────────────────────────────────────────────────────────────
async function fetchJobs() {
  try {
    loading.value = true
    jobs.value = await api.heartbeatJobs.list() as HeartbeatJob[]
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to load jobs')
  } finally {
    loading.value = false
  }
}

// ── Form helpers ───────────────────────────────────────────────────────────
function openCreateDialog() {
  editingJob.value = null
  form.name = ''
  form.prompt = ''
  scheduleSelection.value = '1h'
  form.schedule_value = ''
  showFormDialog.value = true
}

function openEditDialog(job: HeartbeatJob) {
  editingJob.value = job
  form.name = job.name
  form.prompt = job.prompt
  const isPreset = PRESET_OPTIONS.some(o => o.value === job.schedule_value)
  scheduleSelection.value = isPreset ? job.schedule_value : '__cron__'
  form.schedule_value = job.schedule_value
  showFormDialog.value = true
}

async function saveJob() {
  if (!form.name.trim() || !form.prompt.trim()) {
    toast.error('Name and prompt are required')
    return
  }

  const scheduleType = scheduleSelection.value === '__cron__' ? 'cron' : 'preset'
  const scheduleValue = scheduleSelection.value === '__cron__' ? form.schedule_value : scheduleSelection.value

  if (!scheduleValue.trim()) {
    toast.error('Schedule is required')
    return
  }

  try {
    saving.value = true
    if (editingJob.value) {
      const updated = await api.heartbeatJobs.update(editingJob.value.id, {
        name: form.name,
        prompt: form.prompt,
        schedule_type: scheduleType,
        schedule_value: scheduleValue,
      }) as HeartbeatJob
      const idx = jobs.value.findIndex(j => j.id === editingJob.value!.id)
      if (idx !== -1) jobs.value[idx] = updated
      toast.success('Job updated')
    } else {
      const created = await api.heartbeatJobs.create({
        name: form.name,
        prompt: form.prompt,
        schedule_type: scheduleType,
        schedule_value: scheduleValue,
      }) as HeartbeatJob
      jobs.value.unshift(created)
      toast.success('Job created')
    }
    showFormDialog.value = false
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to save job')
  } finally {
    saving.value = false
  }
}

// ── Toggle ─────────────────────────────────────────────────────────────────
async function handleToggle(job: HeartbeatJob) {
  try {
    const updated = await api.heartbeatJobs.toggle(job.id, !job.is_active) as HeartbeatJob
    const idx = jobs.value.findIndex(j => j.id === job.id)
    if (idx !== -1) jobs.value[idx] = updated
    toast.success(updated.is_active ? `${job.name} activated` : `${job.name} deactivated`)
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to update job')
  }
}

// ── Trigger ────────────────────────────────────────────────────────────────
async function handleTrigger(job: HeartbeatJob) {
  try {
    await api.heartbeatJobs.triggerRun(job.id)
    toast.success(`${job.name} triggered`)
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to trigger job')
  }
}

// ── Run History ────────────────────────────────────────────────────────────
async function openRunHistory(job: HeartbeatJob) {
  historyJob.value = job
  runsPage.value = 0
  expandedRuns.value = new Set()
  showRunHistoryDialog.value = true
  await loadRuns(0)
}

async function loadRuns(page: number) {
  if (!historyJob.value) return
  try {
    runsLoading.value = true
    runsPage.value = page
    const result = await api.heartbeatJobs.listRuns(historyJob.value.id, runsPageSize, page * runsPageSize) as HeartbeatJobRunListResponse
    runs.value = result.runs
    runsTotal.value = result.total
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to load runs')
  } finally {
    runsLoading.value = false
  }
}

function toggleRunExpand(runId: string) {
  if (expandedRuns.value.has(runId)) {
    expandedRuns.value.delete(runId)
  } else {
    expandedRuns.value.add(runId)
  }
}

// ── Delete ─────────────────────────────────────────────────────────────────
function openDeleteDialog(job: HeartbeatJob) {
  deletingJob.value = job
  showDeleteDialog.value = true
}

async function confirmDelete() {
  if (!deletingJob.value) return
  try {
    deleting.value = true
    await api.heartbeatJobs.remove(deletingJob.value.id)
    jobs.value = jobs.value.filter(j => j.id !== deletingJob.value!.id)
    toast.success(`${deletingJob.value.name} deleted`)
    showDeleteDialog.value = false
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to delete job')
  } finally {
    deleting.value = false
  }
}

// ── Formatting ─────────────────────────────────────────────────────────────
function formatRelative(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = date.getTime() - now.getTime()
  const absDiff = Math.abs(diffMs)
  const past = diffMs < 0

  if (absDiff < 60_000) return past ? 'just now' : 'in a moment'
  if (absDiff < 3_600_000) {
    const mins = Math.round(absDiff / 60_000)
    return past ? `${mins}m ago` : `in ${mins}m`
  }
  if (absDiff < 86_400_000) {
    const hrs = Math.round(absDiff / 3_600_000)
    return past ? `${hrs}h ago` : `in ${hrs}h`
  }
  const days = Math.round(absDiff / 86_400_000)
  return past ? `${days}d ago` : `in ${days}d`
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString()
}
</script>
