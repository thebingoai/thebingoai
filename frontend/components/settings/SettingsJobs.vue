<template>
  <div class="p-6">
    <!-- Header -->
    <div class="mb-4">
      <h2 class="text-2xl font-medium text-gray-900 dark:text-white select-none">Jobs</h2>
    </div>

    <!-- Tab bar -->
    <div class="flex items-center justify-between mb-6 border-b border-gray-200">
      <div class="flex gap-0">
        <button
          type="button"
          @click="activeTab = 'jobs'"
          class="px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors"
          :class="activeTab === 'jobs' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
        >
          Jobs
        </button>
        <button
          type="button"
          @click="activeTab = 'pipelines'"
          class="px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors"
          :class="activeTab === 'pipelines' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
        >
          Dashboard Pipelines
        </button>
      </div>
      <UiButton v-if="activeTab === 'jobs'" size="sm" class="mb-1" @click="openCreateDialog">
        Create Job
      </UiButton>
    </div>

    <!-- Jobs tab -->
    <div v-if="activeTab === 'jobs'">
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
        class="rounded-lg border transition-colors"
        :class="expandedJobId === job.id ? 'border-blue-200 bg-white dark:bg-neutral-800' : 'border-gray-200 bg-white dark:bg-neutral-800'"
      >
        <div class="flex items-center gap-3 px-4 py-3">
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
              <p class="text-sm font-medium text-gray-900 dark:text-white truncate">{{ job.name || 'Unnamed job' }}</p>
              <button
                type="button"
                :title="expandedJobId === job.id ? 'Close schedule editor' : 'Edit schedule'"
                @click="toggleJobExpand(job.id)"
                class="shrink-0 text-xs px-2 py-0.5 rounded-full font-mono transition-colors"
                :class="expandedJobId === job.id
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-blue-50 hover:text-blue-600'"
              >
                {{ job.cron_expression }}
              </button>
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
              title="Edit name & prompt"
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

        <!-- Inline schedule editor -->
        <ScheduleEditor
          v-if="expandedJobId === job.id"
          :schedule-type="job.schedule_type"
          :schedule-value="job.schedule_value"
          :saving="savingJobSchedule"
          @save="(type, value) => handleJobScheduleSave(job, type, value)"
          @cancel="expandedJobId = null"
        />
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
          <label class="block text-sm font-medium text-gray-700 dark:text-neutral-300 mb-1">Name</label>
          <input
            v-model="form.name"
            type="text"
            placeholder="e.g. Daily standup summary"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:bg-neutral-700 dark:border-neutral-600 dark:text-neutral-100 dark:placeholder-neutral-500 dark:focus:border-blue-400"
          />
        </div>

        <!-- Schedule only shown when creating (editing uses inline row expansion) -->
        <div v-if="!editingJob">
          <label class="block text-sm font-medium text-gray-700 dark:text-neutral-300 mb-1">Schedule</label>
          <select
            v-model="scheduleSelection"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:bg-neutral-700 dark:border-neutral-600 dark:text-neutral-100 dark:focus:border-blue-400"
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
            class="mt-2 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:bg-neutral-700 dark:border-neutral-600 dark:text-neutral-100 dark:placeholder-neutral-500 dark:focus:border-blue-400"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-neutral-300 mb-1">Prompt</label>
          <textarea
            v-model="form.prompt"
            rows="6"
            placeholder="What should the AI do when this job runs? e.g. Summarize any new tasks from my database and send me a brief report."
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none dark:bg-neutral-700 dark:border-neutral-600 dark:text-neutral-100 dark:placeholder-neutral-500 dark:focus:border-blue-400"
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

    <!-- ── Dashboard Pipelines ──────────────────────────────────────────── -->
    <div v-if="activeTab === 'pipelines'">
      <div class="mb-4">
        <p class="text-sm text-gray-500">Scheduled refresh pipelines that keep dashboard widgets up-to-date automatically.</p>
      </div>

      <div v-if="dashboardsLoading" class="space-y-3">
        <UiSkeleton class="h-16 w-full rounded-lg" />
        <UiSkeleton class="h-16 w-full rounded-lg" />
      </div>

      <UiEmptyState
        v-else-if="scheduledDashboards.length === 0"
        title="No dashboard pipelines"
        description="Open a dashboard and click the clock icon to set a refresh schedule."
        :icon="LayoutDashboard"
      />

      <div v-else class="space-y-2">
        <div
          v-for="dashboard in scheduledDashboards"
          :key="dashboard.id"
          class="rounded-lg border transition-colors"
          :class="expandedDashboardId === dashboard.id ? 'border-violet-200 bg-white' : 'border-gray-200'"
        >
          <div class="flex items-center gap-3 px-4 py-3">
            <!-- Active toggle -->
            <button
              type="button"
              :title="dashboard.schedule_active ? 'Deactivate pipeline' : 'Activate pipeline'"
              @click="handleDashboardToggle(dashboard)"
              class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors"
              :class="dashboard.schedule_active ? 'bg-violet-500' : 'bg-gray-200'"
            >
              <span
                class="inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform"
                :class="dashboard.schedule_active ? 'translate-x-4' : 'translate-x-0.5'"
              />
            </button>

            <!-- Dashboard info -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <p class="text-sm font-medium text-gray-900 truncate">{{ dashboard.title }}</p>
                <button
                  type="button"
                  :title="expandedDashboardId === dashboard.id ? 'Close schedule editor' : 'Edit schedule'"
                  @click="toggleDashboardExpand(dashboard.id)"
                  class="shrink-0 text-xs px-2 py-0.5 rounded-full font-mono transition-colors"
                  :class="expandedDashboardId === dashboard.id
                    ? 'bg-violet-100 text-violet-700'
                    : 'bg-violet-50 text-violet-600 hover:bg-violet-100'"
                >
                  {{ dashboard.cron_expression }}
                </button>
                <span class="shrink-0 text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">Dashboard</span>
              </div>
              <p class="text-xs text-gray-400 mt-0.5">
                <span v-if="dashboard.last_run_at">Last: {{ formatRelative(dashboard.last_run_at) }} · </span>
                <span v-if="dashboard.next_run_at && dashboard.schedule_active">Next: {{ formatRelative(dashboard.next_run_at) }}</span>
                <span v-else-if="!dashboard.schedule_active" class="text-gray-300">Inactive</span>
              </p>
            </div>

            <!-- Actions -->
            <div class="flex items-center gap-1 shrink-0">
              <button
                type="button"
                title="Edit schedule"
                @click="toggleDashboardExpand(dashboard.id)"
                class="rounded-lg p-1.5 transition-colors"
                :class="expandedDashboardId === dashboard.id
                  ? 'text-violet-600 bg-violet-50'
                  : 'text-gray-400 hover:bg-gray-100 hover:text-gray-700'"
              >
                <component :is="Pencil" class="h-4 w-4" />
              </button>
              <button
                type="button"
                title="View run history"
                @click="openDashboardRunHistory(dashboard)"
                class="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
              >
                <component :is="History" class="h-4 w-4" />
              </button>
              <button
                type="button"
                title="Trigger now"
                @click="handleDashboardTrigger(dashboard)"
                class="rounded-lg p-1.5 text-gray-400 hover:bg-violet-50 hover:text-violet-600 transition-colors"
              >
                <component :is="Play" class="h-4 w-4" />
              </button>
              <button
                type="button"
                title="Remove schedule"
                @click="handleDashboardRemoveSchedule(dashboard)"
                class="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors"
              >
                <component :is="Trash2" class="h-4 w-4" />
              </button>
            </div>
          </div>

          <!-- Inline schedule editor -->
          <ScheduleEditor
            v-if="expandedDashboardId === dashboard.id"
            :schedule-type="(dashboard.schedule_type as 'preset' | 'cron') || 'cron'"
            :schedule-value="dashboard.schedule_value || dashboard.cron_expression || ''"
            :saving="savingDashboardSchedule"
            @save="(type, value) => handleDashboardScheduleSave(dashboard, type, value)"
            @cancel="expandedDashboardId = null"
          />
        </div>
      </div>
    </div>

    <!-- Dashboard Run History Dialog -->
    <UiDialog
      v-model:open="showDashboardRunHistoryDialog"
      :title="`Refresh History — ${dashboardHistoryItem?.title}`"
      size="xl"
    >
      <div v-if="dashboardRunsLoading" class="space-y-2">
        <UiSkeleton class="h-12 w-full rounded-lg" />
        <UiSkeleton class="h-12 w-full rounded-lg" />
      </div>

      <UiEmptyState
        v-else-if="dashboardRuns.length === 0"
        title="No refresh runs yet"
        description="This dashboard hasn't been refreshed by the schedule yet."
        :icon="History"
      />

      <div v-else class="space-y-2">
        <div
          v-for="run in dashboardRuns"
          :key="run.id"
          class="rounded-lg border border-gray-200 overflow-hidden"
        >
          <div
            class="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors"
            @click="toggleRunExpand(run.id)"
          >
            <span
              class="text-xs font-medium px-2 py-0.5 rounded-full"
              :class="{
                'bg-green-100 text-green-700': run.status === 'completed' && !run.widgets_failed,
                'bg-yellow-100 text-yellow-700': run.status === 'completed' && run.widgets_failed,
                'bg-red-100 text-red-700': run.status === 'failed',
                'bg-blue-100 text-blue-700': run.status === 'running',
              }"
            >
              {{ run.status }}
            </span>
            <span class="text-sm text-gray-700 flex-1">{{ formatDate(run.started_at) }}</span>
            <span v-if="run.widgets_total" class="text-xs text-gray-500">
              {{ run.widgets_succeeded }}/{{ run.widgets_total }} widgets
            </span>
            <span v-if="run.duration_ms" class="text-xs text-gray-400">{{ run.duration_ms }}ms</span>
            <component :is="ChevronDown" class="h-4 w-4 text-gray-400 transition-transform" :class="{ 'rotate-180': expandedRuns.has(run.id) }" />
          </div>
          <div v-if="expandedRuns.has(run.id)" class="border-t border-gray-100 px-4 py-3 space-y-3 bg-gray-50">
            <div v-if="run.error">
              <p class="text-xs font-medium text-red-500 mb-1">Error</p>
              <p class="text-sm text-red-600 font-mono">{{ run.error }}</p>
            </div>
            <div v-if="run.widget_errors && Object.keys(run.widget_errors).length">
              <p class="text-xs font-medium text-gray-500 mb-1">Widget errors</p>
              <div v-for="(errMsg, widgetId) in run.widget_errors" :key="widgetId" class="text-xs text-red-600 font-mono">
                <span class="text-gray-500">{{ widgetId }}:</span> {{ errMsg }}
              </div>
            </div>
            <div v-if="!run.error && (!run.widget_errors || !Object.keys(run.widget_errors).length)">
              <p class="text-xs text-gray-400">All widgets refreshed successfully.</p>
            </div>
          </div>
        </div>

        <div v-if="dashboardRunsTotalPages > 1" class="flex justify-center gap-2 pt-2">
          <UiButton size="sm" variant="outline" :disabled="dashboardRunsPage === 0" @click="loadDashboardRuns(dashboardRunsPage - 1)">Previous</UiButton>
          <UiButton size="sm" variant="outline" :disabled="dashboardRunsPage >= dashboardRunsTotalPages - 1" @click="loadDashboardRuns(dashboardRunsPage + 1)">Next</UiButton>
        </div>
      </div>

      <template #footer>
        <UiButton variant="outline" @click="showDashboardRunHistoryDialog = false">Close</UiButton>
      </template>
    </UiDialog>
  </div>
</template>

<script setup lang="ts">
import { Timer, Pencil, History, Play, Trash2, ChevronDown, LayoutDashboard } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { HeartbeatJob, HeartbeatJobRun, HeartbeatJobRunListResponse } from '~/types/heartbeat'
import type { Dashboard, DashboardRefreshRun } from '~/types/dashboard'
import { PRESET_OPTIONS } from '~/types/heartbeat'
import { parseUtcDate } from '~/utils/format'
import { useDashboardStore } from '~/stores/dashboard'

const api = useApi()
const dashboardStore = useDashboardStore()

// ── Tabs ───────────────────────────────────────────────────────────────────
const activeTab = ref<'jobs' | 'pipelines'>('jobs')

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

// ── Inline expansion ───────────────────────────────────────────────────────
const expandedJobId = ref<string | null>(null)
const savingJobSchedule = ref(false)
const expandedDashboardId = ref<number | null>(null)
const savingDashboardSchedule = ref(false)

// ── Dashboard pipeline state ───────────────────────────────────────────────
const dashboardsLoading = ref(true)
const scheduledDashboards = computed(() =>
  dashboardStore.dashboards.filter(d => d.cron_expression)
)

// Dashboard run history
const showDashboardRunHistoryDialog = ref(false)
const dashboardHistoryItem = ref<Dashboard | null>(null)
const dashboardRuns = ref<DashboardRefreshRun[]>([])
const dashboardRunsLoading = ref(false)
const dashboardRunsPage = ref(0)
const dashboardRunsTotal = ref(0)
const dashboardRunsPageSize = 10
const dashboardRunsTotalPages = computed(() => Math.ceil(dashboardRunsTotal.value / dashboardRunsPageSize))

// ── Lifecycle ──────────────────────────────────────────────────────────────
onMounted(async () => {
  await Promise.all([fetchJobs(), fetchDashboards()])
})

async function fetchDashboards() {
  try {
    dashboardsLoading.value = true
    await dashboardStore.fetchDashboards()
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to load dashboards')
  } finally {
    dashboardsLoading.value = false
  }
}

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

// ── Inline expansion helpers ───────────────────────────────────────────────
function toggleJobExpand(jobId: string) {
  expandedJobId.value = expandedJobId.value === jobId ? null : jobId
}

function toggleDashboardExpand(dashboardId: number) {
  expandedDashboardId.value = expandedDashboardId.value === dashboardId ? null : dashboardId
}

async function handleJobScheduleSave(job: HeartbeatJob, scheduleType: string, scheduleValue: string) {
  try {
    savingJobSchedule.value = true
    const updated = await api.heartbeatJobs.update(job.id, {
      schedule_type: scheduleType as 'preset' | 'cron',
      schedule_value: scheduleValue,
    }) as HeartbeatJob
    const idx = jobs.value.findIndex(j => j.id === job.id)
    if (idx !== -1) jobs.value[idx] = updated
    expandedJobId.value = null
    toast.success('Schedule updated')
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to update schedule')
  } finally {
    savingJobSchedule.value = false
  }
}

async function handleDashboardScheduleSave(dashboard: Dashboard, scheduleType: string, scheduleValue: string) {
  try {
    savingDashboardSchedule.value = true
    await dashboardStore.setSchedule(dashboard.id, scheduleType, scheduleValue)
    expandedDashboardId.value = null
    toast.success('Schedule updated')
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to update schedule')
  } finally {
    savingDashboardSchedule.value = false
  }
}

// ── Dashboard pipeline actions ──────────────────────────────────────────────
async function handleDashboardToggle(dashboard: Dashboard) {
  try {
    await dashboardStore.toggleSchedule(dashboard.id, !dashboard.schedule_active)
    toast.success(dashboard.schedule_active ? `${dashboard.title} pipeline deactivated` : `${dashboard.title} pipeline activated`)
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to toggle pipeline')
  }
}

async function handleDashboardTrigger(dashboard: Dashboard) {
  try {
    await api.dashboards.triggerRefresh(dashboard.id)
    toast.success(`${dashboard.title} refresh triggered`)
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to trigger refresh')
  }
}

async function handleDashboardRemoveSchedule(dashboard: Dashboard) {
  try {
    await dashboardStore.removeSchedule(dashboard.id)
    toast.success(`${dashboard.title} schedule removed`)
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to remove schedule')
  }
}

async function openDashboardRunHistory(dashboard: Dashboard) {
  dashboardHistoryItem.value = dashboard
  dashboardRunsPage.value = 0
  expandedRuns.value = new Set()
  showDashboardRunHistoryDialog.value = true
  await loadDashboardRuns(0)
}

async function loadDashboardRuns(page: number) {
  if (!dashboardHistoryItem.value) return
  try {
    dashboardRunsLoading.value = true
    dashboardRunsPage.value = page
    const result = await api.dashboards.listRefreshRuns(
      dashboardHistoryItem.value.id,
      dashboardRunsPageSize,
      page * dashboardRunsPageSize
    ) as { runs: DashboardRefreshRun[]; total: number }
    dashboardRuns.value = result.runs
    dashboardRunsTotal.value = result.total
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to load runs')
  } finally {
    dashboardRunsLoading.value = false
  }
}

// ── Formatting ─────────────────────────────────────────────────────────────
function formatRelative(dateStr: string): string {
  const date = parseUtcDate(dateStr)
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
  return parseUtcDate(dateStr).toLocaleString()
}
</script>
