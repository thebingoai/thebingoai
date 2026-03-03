<template>
  <div class="flex flex-1 overflow-hidden">
    <!-- Main content area -->
    <div class="flex flex-1 flex-col overflow-hidden min-w-0 min-h-0">

      <!-- List view -->
      <template v-if="!store.currentDashboard">
        <div class="flex-shrink-0 px-6 pt-6 pb-4">
          <h1 class="text-base font-semibold text-gray-900">Dashboards</h1>
        </div>
        <div class="flex-1 overflow-y-auto px-6 pb-6">
          <DashboardListView
            :items="dashboardListItems"
            @open="store.openDashboard"
          />
        </div>
      </template>

      <!-- Dashboard drill-down view -->
      <template v-else>
        <!-- Title bar: back + title + edit toggle -->
        <DashboardTitleBar
          :title="store.currentDashboard.title"
          :edit-mode="store.editMode"
          @back="store.closeDashboard()"
          @toggle-edit="store.toggleEditMode()"
        />

        <!-- Edit toolbar (visible only in edit mode) -->
        <DashboardToolbar
          v-if="store.editMode"
          @add-widget="store.addWidget"
        />

        <!-- Grid -->
        <div class="flex-1 overflow-y-auto p-4">
          <DashboardGrid
            :widgets="store.currentWidgets"
            :edit-mode="store.editMode"
          />
        </div>
      </template>
    </div>

    <!-- Right-side vertical tabs -->
    <div class="flex w-14 flex-shrink-0 flex-col border-l border-gray-200 bg-white py-3">
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
import { LayoutGrid, Clock, Activity } from 'lucide-vue-next'
import { useDashboardStore } from '~/stores/dashboard'
import { toDashboardListItem } from '~/types/dashboard'
import { sampleDashboard } from '~/constants/sampleDashboard'

const store = useDashboardStore()

// Load sample data on mount (Phase 2 will replace this with API fetch)
onMounted(() => {
  if (store.dashboards.length === 0) {
    store.setDashboards([sampleDashboard])
  }
})

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
