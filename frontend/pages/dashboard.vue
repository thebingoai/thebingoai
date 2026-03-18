<template>
  <div class="flex flex-1 overflow-hidden">
    <!-- Main content area -->
    <div class="flex flex-1 flex-col overflow-hidden min-w-0 min-h-0 relative">

      <!-- List view -->
      <template v-if="!store.currentDashboard">
        <div class="flex-shrink-0 px-6 pt-6 pb-4">
          <h1 class="text-base font-semibold text-gray-900">Dashboards</h1>
        </div>
        <div class="flex-1 overflow-y-auto px-6 pb-6">
          <div v-if="store.loading" class="flex items-center justify-center py-16 text-sm text-gray-400">
            Loading dashboards...
          </div>
          <DashboardListView
            v-else
            :items="dashboardListItems"
            @open="store.openDashboard"
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
              @close="configEditorWidget = null"
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

    <!-- Right-side vertical tabs -->
    <div v-if="!store.currentDashboard" class="flex w-14 flex-shrink-0 flex-col border-l border-gray-200 bg-white py-3">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        @click="activeTab = tab.id; if (tab.id !== 'all') store.closeDashboard()"
        class="flex flex-col items-center gap-1 px-1 py-3 transition-colors"
        :class="activeTab === tab.id ? 'text-gray-900' : 'text-gray-400 hover:text-gray-600'"
      >
        <div
          class="flex h-7 w-7 items-center justify-center rounded-lg transition-colors"
          :class="activeTab === tab.id ? 'bg-gray-100' : ''"
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

const dashboardListItems = computed(() =>
  store.dashboards.map(toDashboardListItem),
)

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
