<template>
  <div class="border-b border-gray-100">
    <!-- Header -->
    <button
      @click="chatStore.toggleInfoSection('dashboards')"
      class="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
    >
      <div class="flex items-center gap-1.5">
        <span class="text-[10px] uppercase tracking-wider text-gray-400 font-semibold">Dashboards</span>
        <span v-if="dashboards.length" class="text-[9px] bg-gray-100 text-gray-500 px-1.5 py-px rounded-full">
          {{ dashboards.length }}
        </span>
      </div>
      <svg
        class="w-3 h-3 text-gray-300 transition-transform duration-200"
        :class="{ 'rotate-180': chatStore.infoPanelSections.dashboards }"
        fill="none" viewBox="0 0 24 24" stroke="currentColor"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Content -->
    <div v-show="chatStore.infoPanelSections.dashboards" class="px-4 pb-3">
      <!-- Empty state -->
      <div v-if="!dashboards.length" class="text-center py-4">
        <svg class="w-5 h-5 mx-auto text-gray-200 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <p class="text-[11px] text-gray-300">No dashboards created yet</p>
      </div>

      <!-- Dashboard list -->
      <div v-else class="flex flex-col gap-1.5">
        <div
          v-for="(db, idx) in dashboards"
          :key="idx"
          class="flex items-center justify-between rounded-lg bg-gray-50 px-2.5 py-2"
        >
          <div class="flex items-center gap-2 min-w-0">
            <svg class="w-4 h-4 text-indigo-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <div class="min-w-0">
              <p class="text-[11px] font-medium text-gray-600 truncate">{{ db.name }}</p>
              <p class="text-[10px] text-gray-300">{{ db.widgetCount }} widget{{ db.widgetCount !== 1 ? 's' : '' }}</p>
            </div>
          </div>
          <button
            v-if="db.dashboardId"
            @click="navigateTo(db.dashboardId ? `/dashboard?id=${db.dashboardId}` : '/dashboard')"
            class="text-[10px] text-indigo-500 font-medium hover:text-indigo-600 shrink-0 ml-2"
          >
            View &rarr;
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const chatStore = useChatStore()

const dashboards = computed(() => chatStore.conversationDashboards)
</script>
