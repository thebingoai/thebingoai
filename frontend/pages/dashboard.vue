<template>
  <div class="flex flex-1 overflow-hidden">
    <!-- Main content area -->
    <div class="flex flex-1 flex-col overflow-hidden min-w-0 min-h-0 relative">

      <!-- List view -->
      <template v-if="!store.currentDashboard">
        <div class="flex-shrink-0 px-3 md:px-6 pt-6 pb-4">
          <h1 class="text-base font-semibold text-gray-900 dark:text-neutral-100">Dashboards</h1>
        </div>

        <!-- Mobile horizontal tabs -->
        <div v-if="isMobile" class="flex border-b border-gray-200 px-3 pb-1 gap-4 shrink-0 dark:border-neutral-700">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            @click="activeTab = tab.id"
            class="flex items-center gap-1.5 py-2.5 text-xs transition-colors border-b-2"
            :class="activeTab === tab.id ? 'text-gray-900 border-gray-900' : 'text-gray-400 border-transparent'"
          >
            <component :is="tab.icon" class="h-3.5 w-3.5" />
            {{ tab.label }}
          </button>
        </div>

        <div class="flex-1 overflow-y-auto px-3 md:px-6 pt-4 pb-6">
          <div v-if="store.loading" class="flex items-center justify-center py-16 text-sm text-gray-400">
            Loading dashboards...
          </div>
          <DashboardListView
            v-else
            :items="dashboardListItems"
            @open="store.openDashboard"
            @duplicate="handleDuplicate"
          />
        </div>
      </template>

      <!-- Dashboard drill-down view -->
      <template v-else>
        <!-- Title bar: back + title + edit toggle + save -->
        <DashboardTitleBar
          :title="store.currentDashboard.title"
          :edit-mode="store.editMode"
          :dirty="store.dirty"
          :saving="store.saving"
          :refreshing="store.refreshing"
          :dashboard-id="store.currentDashboard.id"
          @back="store.closeDashboard()"
          @toggle-edit="store.toggleEditMode()"
          @save="store.saveDashboard()"
          @refresh-all="store.refreshAllWidgets()"
          @delete="handleDeleteRequest"
          @update:title="handleTitleUpdate"
        />

        <!-- Edit toolbar (visible only in edit mode) -->
        <DashboardToolbar
          v-if="store.editMode"
          @add-widget="store.addWidget"
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

    <!-- Right-side vertical tabs (desktop only) -->
    <div v-if="!store.currentDashboard && !isMobile" class="flex w-14 flex-shrink-0 flex-col border-l border-gray-200 bg-white py-3 dark:border-neutral-700 dark:bg-neutral-900">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        @click="activeTab = tab.id; if (tab.id !== 'all') store.closeDashboard()"
        class="flex flex-col items-center gap-1 px-1 py-3 transition-colors"
        :class="activeTab === tab.id ? 'text-gray-900 dark:text-neutral-100' : 'text-gray-400 hover:text-gray-600 dark:text-neutral-500 dark:hover:text-neutral-300'"
      >
        <div
          class="flex h-7 w-7 items-center justify-center rounded-lg transition-colors"
          :class="activeTab === tab.id ? 'bg-gray-100 dark:bg-neutral-700' : ''"
        >
          <component :is="tab.icon" class="h-4 w-4" />
        </div>
        <span class="text-[10px] font-light leading-none">{{ tab.label }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { LayoutGrid, Clock, Activity } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useDashboardStore } from '~/stores/dashboard'
import { toDashboardListItem } from '~/types/dashboard'
import type { DashboardWidget } from '~/types/dashboard'
import DashboardWidgetEditor from '~/components/dashboard/editors/DashboardWidgetEditor.vue'

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

const sqlEditorWidget = ref<DashboardWidget | null>(null)
const sqlEditorError = ref<string | null>(null)
const configEditorWidget = ref<DashboardWidget | null>(null)

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

async function handleDuplicate(id: number) {
  try {
    await store.duplicateDashboard(id)
    toast.success('Dashboard duplicated')
  } catch {
    toast.error('Failed to duplicate dashboard')
  }
}

const dashboardListItems = computed(() => {
  let filtered = store.dashboards

  if (activeTab.value === 'recent') {
    filtered = [...filtered]
      .sort((a, b) => {
        const aTime = a.updatedAt ? new Date(a.updatedAt).getTime() : 0
        const bTime = b.updatedAt ? new Date(b.updatedAt).getTime() : 0
        return bTime - aTime
      })
      .slice(0, 10)
  } else if (activeTab.value === 'live') {
    filtered = filtered.filter(d => d.schedule_active === true)
  }

  return filtered.map(toDashboardListItem)
})

const tabs = [
  { id: 'all', label: 'All', icon: LayoutGrid },
  { id: 'recent', label: 'Recent', icon: Clock },
  { id: 'live', label: 'Live', icon: Activity },
]

const activeTab = ref('all')

definePageMeta({
  middleware: 'auth',
})
</script>

<style scoped>
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
