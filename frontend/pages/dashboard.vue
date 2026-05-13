<template>
  <div class="flex flex-1 overflow-hidden">
    <!-- Main content area -->
    <div class="flex flex-1 flex-col overflow-hidden min-w-0 min-h-0 relative">

      <!-- List view -->
      <template v-if="!store.currentDashboard">

        <div class="flex-1 overflow-y-auto px-3 md:px-6 pt-4 pb-6">
          <div v-if="store.loading" class="flex items-center justify-center py-16 text-sm text-gray-400">
            Loading dashboards...
          </div>

          <!-- Empty state -->
          <div v-else-if="store.dashboards.length === 0" class="dashboard-empty">
            <!-- Top header strip -->
            <div class="dashboard-empty-header">
              <div class="eyebrow">DASHBOARDS</div>
              <h1 class="dashboard-empty-title">Nothing saved here yet.</h1>
            </div>

            <!-- Editorial hero block + composer (centered column) -->
            <div class="dashboard-empty-body">
              <div class="eyebrow eyebrow--ember">HOW DASHBOARDS WORK IN BINGO</div>
              <h2 class="dashboard-empty-hero">
                Dashboards aren't built — they're <em class="dashboard-empty-em">graduated</em>.
              </h2>
              <p class="dashboard-empty-sub">
                Ask Bingo a question, watch it work, then promote a result to a dashboard
                when you want to track it. The thread that spawned a widget is always one
                click away — every chart remembers where it came from.
              </p>

              <ChatComposer @send="handleEmptyStateSend" />

              <!-- Heads up tip box -->
              <div class="dashboard-empty-tip">
                <Info class="h-3.5 w-3.5 flex-shrink-0 mt-0.5 text-[var(--ink-2)]" />
                <p>
                  <strong>Heads up:</strong> dashboards are <em>shareable</em> by default within
                  your workspace. You can lock to a team or a specific schedule from any
                  dashboard's share menu. Deleting a dashboard never deletes the underlying
                  threads — those stay in your task history.
                </p>
              </div>
            </div>
          </div>

          <!-- Populated state -->
          <div v-else class="dashboard-list">
            <!-- Header -->
            <div class="dashboard-list-header">
              <div class="dashboard-list-header-text">
                <div class="eyebrow">DASHBOARDS</div>
                <h1 class="dashboard-list-title">
                  What we've <em class="dashboard-list-em">figured out</em>.
                </h1>
                <p class="dashboard-list-sub">
                  {{ store.dashboards.length }} dashboard{{ store.dashboards.length === 1 ? '' : 's' }} across your workspace.
                  Each one is rooted in a thread — click "from: …" on any row to jump back to the conversation that spawned it.
                </p>
              </div>
              <div class="dashboard-list-actions">
                <button class="dash-btn dash-btn--ghost" @click="store.fetchDashboards()" :disabled="store.loading">
                  <RefreshCw class="h-3 w-3" :class="{ 'animate-spin': store.loading }" />
                  Refresh all
                </button>
                <button class="dash-btn dash-btn--primary" @click="handleNewDashboard">
                  <Plus class="h-3 w-3" />
                  New dashboard
                </button>
              </div>
            </div>

            <!-- Toolbar -->
            <div class="dashboard-toolbar">
              <div class="dashboard-search">
                <Search class="h-3 w-3 text-[var(--ink-3)] flex-shrink-0" />
                <input v-model="searchQuery" type="text" placeholder="Search dashboards..." class="dashboard-search-input" />
                <span class="dashboard-search-hint">⌘K</span>
              </div>

              <div class="dashboard-pills">
                <button
                  v-for="p in pills"
                  :key="p.id"
                  class="dashboard-pill"
                  :class="{ 'dashboard-pill--active': filterPill === p.id }"
                  @click="filterPill = p.id"
                >
                  <span v-if="p.dot" class="dash-pill-dot" />
                  {{ p.label }}
                </button>
              </div>

              <div class="dashboard-sort">
                <span class="dashboard-sort-label">SORT</span>
                <select v-model="sortBy" class="dashboard-sort-select">
                  <option value="refreshed">Recently refreshed</option>
                  <option value="created">Recently created</option>
                  <option value="title">Title A–Z</option>
                  <option value="widgets">Most widgets</option>
                </select>
                <div class="dashboard-view-toggle" role="group" aria-label="View">
                  <button
                    class="dashboard-view-btn"
                    :class="{ 'dashboard-view-btn--active': view === 'list' }"
                    title="List view"
                    @click="view = 'list'"
                  >
                    <ListIcon class="h-3.5 w-3.5" />
                  </button>
                  <button
                    class="dashboard-view-btn"
                    :class="{ 'dashboard-view-btn--active': view === 'grid' }"
                    title="Grid view"
                    @click="view = 'grid'"
                  >
                    <LayoutGrid class="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>

            <!-- Table or Grid view -->
            <DashboardTable
              v-if="view === 'list'"
              :items="dashboardListItems"
              :current-user-email="authStore.user?.email ?? ''"
              @open="store.openDashboard"
              @open-thread="handleOpenThread"
            />
            <DashboardCardGrid
              v-else
              :items="dashboardListItems"
              :current-user-email="authStore.user?.email ?? ''"
              @open="store.openDashboard"
              @open-thread="handleOpenThread"
            />
          </div>
        </div>
      </template>

      <!-- Dashboard drill-down view -->
      <template v-else>
        <!-- Title bar -->
        <DashboardTitleBar
          :title="store.currentDashboard.title"
          :edit-mode="store.editMode"
          :dirty="store.dirty"
          :saving="store.saving"
          :refreshing="store.refreshing"
          :dashboard-id="store.currentDashboard.id"
          :source-title="dashboardSourceTitle"
          @back="store.closeDashboard()"
          @toggle-edit="store.toggleEditMode()"
          @save="store.saveDashboard()"
          @refresh-all="store.refreshAllWidgets()"
          @delete="handleDeleteRequest"
          @share="handleShare"
          @update:title="handleTitleUpdate"
          @analyze="openAnalyzePanel"
        />

        <!-- Toolbar — always visible -->
        <DashboardToolbar
          :widget-count="store.currentWidgets.length"
          @add-widget="handleAddWidget"
        />

        <!-- Grid + inline editor -->
        <div class="flex flex-1 overflow-hidden">
          <div class="flex-1 overflow-y-auto p-4">
            <DashboardGrid
              :widgets="store.currentWidgets"
              :edit-mode="store.editMode"
              @open-sql-editor="openSqlEditor"
              @edit-config="openConfigEditor"
            />
          </div>
          <Transition name="panel-slide">
            <DashboardWidgetEditor
              v-if="configEditorWidget"
              :widget="configEditorWidget"
              :edit-mode="store.editMode"
              :class="isMobile ? 'fixed inset-0 z-50 w-full' : ''"
              @close="configEditorWidget = null"
              @open-sql-editor="openSqlEditor"
            />
          </Transition>
          <Transition name="panel-slide">
            <DashboardAnalyzePanel
              v-if="analyzePanel"
              :dashboard-id="store.currentDashboard?.id ?? 0"
              :class="isMobile ? 'fixed inset-0 z-50 w-full' : ''"
              @close="analyzePanel = false"
            />
          </Transition>
        </div>
      </template>

      <!-- Delete dashboard confirmation dialog -->
      <UiDialog
        v-model:open="showDeleteDialog"
        title="Delete Dashboard"
        size="sm"
      >
        <div class="space-y-4">
          <p class="text-sm text-gray-600">
            This will permanently delete <span class="font-medium text-gray-900">{{ store.currentDashboard?.title }}</span> and all its widgets. This action cannot be undone.
          </p>
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">
              Type <span class="font-semibold">{{ store.currentDashboard?.title }}</span> to confirm
            </label>
            <input
              v-model="deleteConfirmText"
              type="text"
              placeholder="Dashboard name"
              class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-red-400 focus:outline-none focus:ring-1 focus:ring-red-400"
            />
          </div>
        </div>
        <template #footer>
          <UiButton variant="outline" size="sm" @click="showDeleteDialog = false">Cancel</UiButton>
          <UiButton
            variant="danger"
            size="sm"
            :disabled="deleteConfirmText !== store.currentDashboard?.title"
            :loading="deleting"
            @click="confirmDelete"
          >Delete</UiButton>
        </template>
      </UiDialog>

      <!-- SQL editor modal -->
      <DashboardSqlEditor
        v-if="sqlEditorWidget"
        :widget="sqlEditorWidget"
        :edit-mode="store.editMode"
        :widget-error="sqlEditorError"
        @close="sqlEditorWidget = null; sqlEditorError = null"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Info, Search, Plus, RefreshCw, LayoutGrid, List as ListIcon } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useDashboardStore } from '~/stores/dashboard'
import { toDashboardListItem } from '~/types/dashboard'
import type { DashboardWidget } from '~/types/dashboard'
import DashboardWidgetEditor from '~/components/dashboard/editors/DashboardWidgetEditor.vue'
import DashboardAnalyzePanel from '~/components/dashboard/DashboardAnalyzePanel.vue'
import DashboardTable from '~/components/dashboard/DashboardTable.vue'
import DashboardCardGrid from '~/components/dashboard/DashboardCardGrid.vue'
import ChatComposer from '~/components/chat/ChatComposer.vue'
import { useChatFileUpload } from '~/composables/useChatFileUpload'
import { useChat } from '~/composables/useChat'

const store = useDashboardStore()
const route = useRoute()
const { isMobile } = useIsMobile()

onMounted(async () => {
  await store.fetchDashboards()
  const idParam = route.query.id
  if (idParam) {
    const id = Number(idParam)
    if (!isNaN(id)) store.openDashboard(id)
  }
})

// ── Drill-down state ──────────────────────────────────────
const sqlEditorWidget = ref<DashboardWidget | null>(null)
const sqlEditorError = ref<string | null>(null)
const configEditorWidget = ref<DashboardWidget | null>(null)
const analyzePanel = ref(false)

function openAnalyzePanel() {
  analyzePanel.value = true
}

const showDeleteDialog = ref(false)
const deleteConfirmText = ref('')
const deleting = ref(false)

function handleTitleUpdate(newTitle: string) {
  if (store.currentDashboard) {
    store.currentDashboard.title = newTitle
    store.dirty = true
  }
}

function handleDeleteRequest() {
  deleteConfirmText.value = ''
  showDeleteDialog.value = true
}

async function confirmDelete() {
  const id = store.currentDashboard?.id
  if (!id) return
  deleting.value = true
  try {
    await store.deleteDashboard(id)
    showDeleteDialog.value = false
    toast.success('Dashboard deleted')
  } catch {
    toast.error('Failed to delete dashboard')
  } finally {
    deleting.value = false
  }
}

watch(() => store.editMode, (editing) => {
  if (!editing) configEditorWidget.value = null
})

function openSqlEditor(widgetId: string, error?: string) {
  sqlEditorWidget.value = store.currentWidgets.find(w => w.id === widgetId) ?? null
  sqlEditorError.value = error ?? null
}

function openConfigEditor(widgetId: string) {
  configEditorWidget.value = store.currentWidgets.find(w => w.id === widgetId) ?? null
}

const dashboardSourceTitle = computed(() => {
  const d = store.currentDashboard
  if (!d) return undefined
  const widgetSource = store.currentWidgets.find(w => w.sources?.length)?.sources?.[0]
  return widgetSource
    ?? (d.data_context as any)?.source_title
    ?? (d.data_context as any)?.source_name
    ?? (d.data_context as any)?.source_task
    ?? undefined
})

function handleShare() {
  navigator.clipboard?.writeText(window.location.href)
  toast.success('Link copied to clipboard')
}

function handleAddWidget(type: import('~/types/dashboard').WidgetType) {
  if (!store.editMode) store.toggleEditMode()
  store.addWidget(type)
}

// ── List view state ───────────────────────────────────────
const authStore = useAuthStore()
const chatStore = useChatStore()
const chat = useChat()
const { getFileIds, clearFiles } = useChatFileUpload()

const searchQuery = ref('')
const filterPill = ref<'all' | 'mine' | 'scheduled' | 'shared'>('all')
const sortBy = ref<'refreshed' | 'created' | 'title' | 'widgets'>('refreshed')
const view = ref<'list' | 'grid'>('list')

const pills = [
  { id: 'all',       label: 'All',            dot: false },
  { id: 'mine',      label: 'Mine',           dot: false },
  { id: 'scheduled', label: 'Scheduled',      dot: true  },
  { id: 'shared',    label: 'Shared with me', dot: false },
] as const

const dashboardListItems = computed(() => {
  let list = store.dashboards.map(toDashboardListItem)

  if (filterPill.value === 'scheduled') list = list.filter(d => d.scheduleActive)
  if (filterPill.value === 'shared')    list = []

  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(d =>
      d.title.toLowerCase().includes(q) ||
      (d.sourceTitle ?? '').toLowerCase().includes(q)
    )
  }

  list.sort((a, b) => {
    switch (sortBy.value) {
      case 'refreshed': return new Date(b.updatedAt ?? 0).getTime() - new Date(a.updatedAt ?? 0).getTime()
      case 'created':   return new Date(b.createdAt ?? 0).getTime() - new Date(a.createdAt ?? 0).getTime()
      case 'title':     return a.title.localeCompare(b.title)
      case 'widgets':   return b.widgetCount - a.widgetCount
      default:          return 0
    }
  })
  return list
})

async function handleEmptyStateSend() {
  if (!chatStore.inputText.trim()) return
  const fileIds = getFileIds()
  if (!chatStore.currentThreadId) {
    const tempId = `pending-${Date.now()}`
    chatStore.pendingNewConversationId = tempId
    chatStore.addConversation({
      id: tempId,
      title: chatStore.inputText.trim().substring(0, 80),
      type: 'task',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      message_count: 1,
    })
  }
  chat.sendMessage(chatStore.inputText, fileIds)
  clearFiles()
  if (chatStore.pendingNewConversationId) {
    chatStore.currentThreadId = chatStore.pendingNewConversationId
  }
  await navigateTo('/chat')
}

function handleOpenThread(threadId: string) {
  chat.loadMessages(threadId)
  navigateTo('/chat')
}

async function handleNewDashboard() {
  chat.newChat()
  await navigateTo('/chat')
}

definePageMeta({
  middleware: 'auth',
})
</script>

<style scoped>
/* ── Empty state ────────────────────────────────────────── */
.dashboard-empty {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.dashboard-empty-header {
  padding: 20px 0 16px;
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}

.dashboard-empty-title {
  margin: 8px 0 0;
  font-family: var(--font-display);
  font-size: 30px;
  line-height: 1.05;
  letter-spacing: -0.02em;
  color: var(--ink-0);
  font-weight: 500;
}

.dashboard-empty-body {
  flex: 1;
  overflow-y: auto;
  max-width: 760px;
  width: 100%;
  margin: 0 auto;
  padding: 44px 0 60px;
}

.eyebrow--ember {
  color: var(--ember);
}

.dashboard-empty-hero {
  margin: 16px 0 0;
  font-family: var(--font-display);
  font-size: 48px;
  line-height: 1.05;
  letter-spacing: -0.02em;
  color: var(--ink-0);
  font-weight: 500;
}
.dashboard-empty-em {
  font-style: italic;
  font-weight: 400;
  color: var(--ember);
}

.dashboard-empty-sub {
  font-size: 16px;
  color: var(--ink-1);
  line-height: 1.6;
  max-width: 600px;
  margin-top: 20px;
  margin-bottom: 0;
}

.dashboard-empty-tip {
  display: flex;
  gap: 10px;
  margin-top: 36px;
  padding: 14px 18px;
  border: 1px dashed var(--line);
  border-radius: 12px;
  background: var(--paper-1);
}
.dashboard-empty-tip p {
  margin: 0;
  font-size: 13px;
  color: var(--ink-1);
  line-height: 1.55;
}
.dashboard-empty-tip strong {
  font-weight: 600;
  color: var(--ink-0);
}
.dashboard-empty-tip em {
  font-style: italic;
  color: var(--ink-0);
}

/* ── Populated list ─────────────────────────────────────── */
.dashboard-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.dashboard-list-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 20px 0 20px;
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}

.dashboard-list-header-text {
  flex: 1;
  min-width: 0;
}

.dashboard-list-title {
  margin: 8px 0 0;
  font-family: var(--font-display);
  font-size: 36px;
  line-height: 1.05;
  letter-spacing: -0.02em;
  color: var(--ink-0);
  font-weight: 500;
}

.dashboard-list-em {
  font-style: italic;
  font-weight: 400;
  color: var(--ember);
}

.dashboard-list-sub {
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--ink-2);
  line-height: 1.55;
  max-width: 600px;
}

.dashboard-list-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  margin-top: 14px;
}

.dash-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 13px;
  border-radius: 8px;
  font-size: 12.5px;
  font-weight: 500;
  font-family: var(--font-sans);
  cursor: pointer;
  letter-spacing: -0.005em;
  transition: opacity 0.15s;
  white-space: nowrap;
}
.dash-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.dash-btn--ghost {
  background: var(--paper-0);
  border: 1px solid var(--line-2);
  color: var(--ink-1);
}
.dash-btn--ghost:hover:not(:disabled) {
  background: var(--paper-1);
}
.dash-btn--primary {
  background: var(--ink-0);
  border: 1px solid var(--ink-0);
  color: var(--paper-0);
}
.dash-btn--primary:hover:not(:disabled) {
  opacity: 0.82;
}

/* ── Toolbar ── */
.dashboard-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 0 14px;
  border-bottom: 1px solid var(--line);
  flex-wrap: wrap;
}

.dashboard-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--paper-0);
  width: 260px;
  flex-shrink: 0;
}

.dashboard-search-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  font-size: 12.5px;
  font-family: var(--font-sans);
  color: var(--ink-0);
}
.dashboard-search-input::placeholder {
  color: var(--ink-3);
}

.dashboard-search-hint {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--ink-3);
  flex-shrink: 0;
}

.dashboard-pills {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dashboard-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px;
  border-radius: 999px;
  border: 1px solid var(--line);
  font-size: 12.5px;
  font-family: var(--font-sans);
  color: var(--ink-1);
  background: var(--paper-0);
  cursor: pointer;
  transition: background 0.1s, color 0.1s, border-color 0.1s;
  white-space: nowrap;
}
.dashboard-pill:hover:not(.dashboard-pill--active) {
  background: var(--paper-1);
  border-color: var(--line-2);
}
.dashboard-pill--active {
  background: var(--ink-0);
  color: var(--paper-0);
  border-color: var(--ink-0);
}

.dash-pill-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ember);
  flex-shrink: 0;
}

.dashboard-sort {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}

.dashboard-sort-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.08em;
  color: var(--ink-3);
  text-transform: uppercase;
  flex-shrink: 0;
}

.dashboard-sort-select {
  background: transparent;
  border: none;
  outline: none;
  font-size: 12.5px;
  font-family: var(--font-sans);
  color: var(--ink-1);
  cursor: pointer;
}

/* ── View toggle ── */
.dashboard-view-toggle {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  margin-left: 8px;
}

.dashboard-view-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 26px;
  background: var(--paper-0);
  color: var(--ink-2);
  cursor: pointer;
  border: none;
  transition: background 0.1s, color 0.1s;
}
.dashboard-view-btn + .dashboard-view-btn {
  border-left: 1px solid var(--line);
}
.dashboard-view-btn:hover {
  background: var(--paper-1);
}
.dashboard-view-btn--active {
  background: var(--ink-0);
  color: var(--paper-0);
}

/* ── Gap between toolbar and data renderer ── */
.dash-table,
.dashboard-card-grid {
  margin-top: 16px;
}

/* ── Slide transition for side panels ── */
.panel-slide-enter-active {
  transition: transform 0.2s ease-out, opacity 0.2s ease-out;
}
.panel-slide-leave-active {
  transition: transform 0.15s ease-in, opacity 0.15s ease-in;
}
.panel-slide-enter-from,
.panel-slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
