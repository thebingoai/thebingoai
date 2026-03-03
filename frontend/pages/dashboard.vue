<template>
  <div class="flex flex-1 overflow-hidden">
    <!-- Main dashboard area -->
    <div class="flex flex-1 flex-col overflow-y-auto min-w-0 min-h-0 pt-16 px-6 pb-6">
      <!-- All tab: show all dashboards or drill-down chart grid -->
      <template v-if="activeTab === 'all'">
        <!-- Drill-down: chart grid for selected dashboard -->
        <template v-if="selectedDashboard">
          <div class="mb-5 flex items-center gap-3">
            <button
              @click="selectedDashboard = null"
              class="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-700 transition-colors"
            >
              <ChevronLeft class="h-4 w-4" />
              <span>Dashboards</span>
            </button>
            <span class="text-gray-300">/</span>
            <span class="text-sm font-medium text-gray-800">{{ selectedDashboard.title }}</span>
          </div>
          <div class="grid gap-5 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
            <div v-for="(chart, i) in selectedDashboard.charts" :key="i" class="h-64">
              <DashboardChart :config="chart" class="h-full" />
            </div>
          </div>
        </template>

        <!-- Card list view -->
        <template v-else>
          <div v-if="dashboards.length > 0" class="grid gap-5 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
            <DashboardCard
              v-for="dashboard in dashboards"
              :key="dashboard.id"
              :dashboard="dashboard"
              @click="selectedDashboard = dashboard"
            />
          </div>
          <div v-else class="flex flex-1 flex-col items-center justify-center min-h-[400px]">
            <LayoutGrid class="h-10 w-10 text-gray-200 mb-3" />
            <p class="text-sm font-light text-gray-400">No dashboards yet</p>
          </div>
        </template>
      </template>

      <!-- Recent tab: placeholder -->
      <template v-else-if="activeTab === 'recent'">
        <div class="flex flex-1 flex-col items-center justify-center min-h-[400px]">
          <Clock class="h-10 w-10 text-gray-200 mb-3" />
          <p class="text-sm font-light text-gray-400">No recent dashboards</p>
        </div>
      </template>

      <!-- Live tab: placeholder -->
      <template v-else-if="activeTab === 'live'">
        <div class="flex flex-1 flex-col items-center justify-center min-h-[400px]">
          <Activity class="h-10 w-10 text-gray-200 mb-3" />
          <p class="text-sm font-light text-gray-400">No live dashboards yet</p>
        </div>
      </template>
    </div>

    <!-- Right-side vertical tabs -->
    <div class="flex w-14 flex-shrink-0 flex-col border-l border-gray-200 bg-white py-3">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        @click="activeTab = tab.id; selectedDashboard = null"
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
import { LayoutGrid, Clock, Activity, ChevronLeft } from 'lucide-vue-next'
import type { DashboardConfig } from '~/types/chart'

const tabs = [
  { id: 'all', label: 'All', icon: LayoutGrid },
  { id: 'recent', label: 'Recent', icon: Clock },
  { id: 'live', label: 'Live', icon: Activity },
]

const activeTab = ref('all')
const selectedDashboard = ref<DashboardConfig | null>(null)

const dashboards: DashboardConfig[] = [
  {
    id: 'sample-1',
    title: 'Business Overview',
    description: 'Key metrics across sales, performance, and distribution',
    createdAt: '2026-03-01',
    charts: [
      {
        type: 'line',
        title: 'Monthly Revenue',
        description: 'Revenue trend over the past 6 months',
        data: {
          labels: ['Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'],
          datasets: [
            {
              label: 'Revenue ($k)',
              data: [42, 55, 61, 48, 70, 83],
              borderColor: '#6366f1',
              backgroundColor: 'rgba(99,102,241,0.1)',
              tension: 0.4,
              fill: false,
              pointRadius: 4,
            },
          ],
        },
        options: { showLegend: false, showGrid: true },
        animation: { entrance: 'slideUp', entranceDuration: 500 },
      },
      {
        type: 'bar',
        title: 'Sales by Region',
        description: 'Units sold per region this quarter',
        data: {
          labels: ['North', 'South', 'East', 'West', 'Central'],
          datasets: [
            {
              label: 'Units',
              data: [320, 210, 480, 390, 150],
              backgroundColor: [
                '#6366f1',
                '#8b5cf6',
                '#a78bfa',
                '#c4b5fd',
                '#ddd6fe',
              ],
              borderWidth: 0,
            },
          ],
        },
        options: { showLegend: false, showGrid: true },
        animation: { entrance: 'slideUp', entranceDuration: 500, entranceDelay: 80 },
      },
      {
        type: 'pie',
        title: 'Product Mix',
        description: 'Share of revenue by product category',
        data: {
          labels: ['Software', 'Services', 'Hardware', 'Support', 'Other'],
          datasets: [
            {
              label: 'Revenue share',
              data: [38, 27, 18, 12, 5],
              backgroundColor: [
                '#6366f1',
                '#8b5cf6',
                '#a78bfa',
                '#c4b5fd',
                '#e0e7ff',
              ],
              borderWidth: 0,
            },
          ],
        },
        options: { showLegend: true, legendPosition: 'bottom' },
        animation: { entrance: 'fadeIn', entranceDuration: 600, entranceDelay: 160 },
      },
      {
        type: 'area',
        title: 'User Growth',
        description: 'Cumulative active users over time',
        data: {
          labels: ['Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'],
          datasets: [
            {
              label: 'Active Users',
              data: [1200, 1850, 2400, 2950, 3700, 4600],
              borderColor: '#10b981',
              backgroundColor: 'rgba(16,185,129,0.15)',
              tension: 0.4,
              fill: true,
              pointRadius: 3,
            },
          ],
        },
        options: { showLegend: false, showGrid: true },
        animation: { entrance: 'slideUp', entranceDuration: 500, entranceDelay: 240 },
      },
      {
        type: 'scatter',
        title: 'Deal Size vs Close Rate',
        description: 'Relationship between deal value and win probability',
        data: {
          labels: ['$10k', '$20k', '$30k', '$40k', '$50k', '$60k'],
          datasets: [
            {
              label: 'Deals',
              data: [12, 28, 45, 38, 60, 22, 50, 15, 32, 18],
              backgroundColor: 'rgba(99,102,241,0.6)',
              pointRadius: 6,
            },
          ],
        },
        options: { showLegend: false, showGrid: true },
        animation: { entrance: 'grow', entranceDuration: 600, entranceDelay: 320 },
      },
    ],
  },
]

definePageMeta({
  middleware: 'auth'
})
</script>
