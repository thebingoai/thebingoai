# Phase 11: Frontend Memory & Usage Dashboards

## Objective

Build memory insights page and usage analytics dashboard with charts, statistics, and cost tracking.

## Prerequisites

- Phase 06: Memory System API
- Phase 07: Token Tracking API
- Phase 09: Frontend Auth (layout, navigation)

## Files to Create

### Pages
- `frontend/pages/memory.vue` - Memory insights page
- `frontend/pages/usage.vue` - Usage analytics dashboard
- `frontend/pages/dashboard.vue` - Overview dashboard (optional)

### Components
- `frontend/components/MemoryCard.vue` - Display memory summary
- `frontend/components/MemorySearch.vue` - Search memories
- `frontend/components/UsageChart.vue` - Chart.js usage visualization
- `frontend/components/UsageStats.vue` - Usage statistics cards
- `frontend/components/CostBreakdown.vue` - Cost breakdown by operation

### Composables
- `frontend/composables/useMemory.ts` - Memory search and management
- `frontend/composables/useUsage.ts` - Usage analytics

### Types
- `frontend/types/memory.ts` - Memory types
- `frontend/types/usage.ts` - Usage types

## Implementation Details

### 1. Memory Composable (frontend/composables/useMemory.ts)

```typescript
import type { Memory, MemorySearchRequest, MemorySearchResponse } from '~/types/memory'

export const useMemory = () => {
  const api = useApi()
  const memories = ref<Memory[]>([])
  const loading = ref(false)

  async function searchMemories(query: string, topK: number = 5) {
    loading.value = true
    try {
      const request: MemorySearchRequest = { query, top_k: topK }
      const response = await api.post<MemorySearchResponse>('/api/memory/search', request)
      memories.value = response.memories
      return response.memories
    } finally {
      loading.value = false
    }
  }

  async function generateMemory(date: string) {
    loading.value = true
    try {
      await api.post('/api/memory/generate', { date })
    } finally {
      loading.value = false
    }
  }

  async function deleteAllMemories() {
    loading.value = true
    try {
      await api.delete('/api/memory')
      memories.value = []
    } finally {
      loading.value = false
    }
  }

  return {
    memories,
    loading,
    searchMemories,
    generateMemory,
    deleteAllMemories
  }
}
```

### 2. Usage Composable (frontend/composables/useUsage.ts)

```typescript
import type { UsageSummary, DailyUsage } from '~/types/usage'

export const useUsage = () => {
  const api = useApi()
  const summary = ref<UsageSummary | null>(null)
  const dailyUsage = ref<DailyUsage[]>([])
  const loading = ref(false)

  async function fetchUsageSummary(days: number = 30) {
    loading.value = true
    try {
      summary.value = await api.get<UsageSummary>(`/api/usage/summary?days=${days}`)
    } finally {
      loading.value = false
    }
  }

  async function fetchDailyUsage(days: number = 30) {
    loading.value = true
    try {
      const response = await api.get<{ daily_usage: DailyUsage[] }>(`/api/usage/daily?days=${days}`)
      dailyUsage.value = response.daily_usage
    } finally {
      loading.value = false
    }
  }

  return {
    summary,
    dailyUsage,
    loading,
    fetchUsageSummary,
    fetchDailyUsage
  }
}
```

### 3. Memory Page (frontend/pages/memory.vue)

```vue
<template>
  <div class="container mx-auto px-4 py-8">
    <h1 class="text-3xl font-bold mb-6">Memory Insights</h1>

    <div class="mb-6">
      <p class="text-gray-600 mb-4">
        The agent learns from your interactions and stores daily summaries to improve future responses.
      </p>

      <button
        @click="handleGenerateMemory"
        class="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 mr-2"
      >
        Generate Today's Memory
      </button>

      <button
        @click="handleDeleteMemories"
        class="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700"
      >
        Delete All Memories
      </button>
    </div>

    <MemorySearch @search="handleSearch" :loading="loading" class="mb-6" />

    <div v-if="memories.length > 0" class="space-y-4">
      <MemoryCard
        v-for="memory in memories"
        :key="memory.id"
        :memory="memory"
      />
    </div>

    <div v-else-if="!loading" class="text-center py-12 text-gray-500">
      No memories found. Try searching or generate today's memory.
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: 'auth'
})

const { memories, loading, searchMemories, generateMemory, deleteAllMemories } = useMemory()

async function handleSearch(query: string) {
  await searchMemories(query)
}

async function handleGenerateMemory() {
  const today = new Date().toISOString().split('T')[0]
  await generateMemory(today)
  alert('Memory generation started. Check back in a few minutes.')
}

async function handleDeleteMemories() {
  if (confirm('Are you sure? This will delete all your memories.')) {
    await deleteAllMemories()
    alert('All memories deleted')
  }
}
</script>
```

### 4. Usage Page (frontend/pages/usage.vue)

```vue
<template>
  <div class="container mx-auto px-4 py-8">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-3xl font-bold">Usage & Costs</h1>

      <select
        v-model="selectedDays"
        @change="handleDaysChange"
        class="rounded-md border-gray-300 shadow-sm"
      >
        <option :value="7">Last 7 days</option>
        <option :value="30">Last 30 days</option>
        <option :value="90">Last 90 days</option>
      </select>
    </div>

    <div v-if="loading" class="text-center py-12">
      <p class="text-gray-500">Loading usage data...</p>
    </div>

    <div v-else-if="summary" class="space-y-6">
      <!-- Stats Cards -->
      <UsageStats :summary="summary" />

      <!-- Daily Usage Chart -->
      <div class="bg-white rounded-lg shadow p-6">
        <h2 class="text-xl font-semibold mb-4">Daily Token Usage</h2>
        <UsageChart :data="dailyUsage" />
      </div>

      <!-- Cost Breakdown -->
      <CostBreakdown :summary="summary" />
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: 'auth'
})

const { summary, dailyUsage, loading, fetchUsageSummary, fetchDailyUsage } = useUsage()

const selectedDays = ref(30)

onMounted(async () => {
  await loadUsageData()
})

async function loadUsageData() {
  await Promise.all([
    fetchUsageSummary(selectedDays.value),
    fetchDailyUsage(selectedDays.value)
  ])
}

async function handleDaysChange() {
  await loadUsageData()
}
</script>
```

### 5. Usage Stats Component (frontend/components/UsageStats.vue)

```vue
<template>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
    <div class="bg-white rounded-lg shadow p-6">
      <div class="flex items-center">
        <div class="flex-1">
          <p class="text-sm text-gray-500">Total Operations</p>
          <p class="text-3xl font-bold text-gray-900">
            {{ summary.totals.operations.toLocaleString() }}
          </p>
        </div>
        <div class="text-indigo-600">
          <svg class="w-12 h-12" fill="currentColor" viewBox="0 0 20 20">
            <path d="M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zM8 7a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zM14 4a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z" />
          </svg>
        </div>
      </div>
    </div>

    <div class="bg-white rounded-lg shadow p-6">
      <div class="flex items-center">
        <div class="flex-1">
          <p class="text-sm text-gray-500">Total Tokens</p>
          <p class="text-3xl font-bold text-gray-900">
            {{ (summary.totals.tokens / 1000).toFixed(1) }}K
          </p>
        </div>
        <div class="text-green-600">
          <svg class="w-12 h-12" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4 2a2 2 0 00-2 2v11a3 3 0 106 0V4a2 2 0 00-2-2H4zm1 14a1 1 0 100-2 1 1 0 000 2zm5-1.757l4.9-4.9a2 2 0 000-2.828L13.485 5.1a2 2 0 00-2.828 0L10 5.757v8.486zM16 18H9.071l6-6H16a2 2 0 012 2v2a2 2 0 01-2 2z" clip-rule="evenodd" />
          </svg>
        </div>
      </div>
    </div>

    <div class="bg-white rounded-lg shadow p-6">
      <div class="flex items-center">
        <div class="flex-1">
          <p class="text-sm text-gray-500">Total Cost</p>
          <p class="text-3xl font-bold text-gray-900">
            ${{ summary.totals.cost.toFixed(4) }}
          </p>
        </div>
        <div class="text-yellow-600">
          <svg class="w-12 h-12" fill="currentColor" viewBox="0 0 20 20">
            <path d="M8.433 7.418c.155-.103.346-.196.567-.267v1.698a2.305 2.305 0 01-.567-.267C8.07 8.34 8 8.114 8 8c0-.114.07-.34.433-.582zM11 12.849v-1.698c.22.071.412.164.567.267.364.243.433.468.433.582 0 .114-.07.34-.433.582a2.305 2.305 0 01-.567.267z" />
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-13a1 1 0 10-2 0v.092a4.535 4.535 0 00-1.676.662C6.602 6.234 6 7.009 6 8c0 .99.602 1.765 1.324 2.246.48.32 1.054.545 1.676.662v1.941c-.391-.127-.68-.317-.843-.504a1 1 0 10-1.51 1.31c.562.649 1.413 1.076 2.353 1.253V15a1 1 0 102 0v-.092a4.535 4.535 0 001.676-.662C13.398 13.766 14 12.991 14 12c0-.99-.602-1.765-1.324-2.246A4.535 4.535 0 0011 9.092V7.151c.391.127.68.317.843.504a1 1 0 101.511-1.31c-.563-.649-1.413-1.076-2.354-1.253V5z" clip-rule="evenodd" />
          </svg>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { UsageSummary } from '~/types/usage'

defineProps<{
  summary: UsageSummary
}>()
</script>
```

### 6. Usage Chart Component (frontend/components/UsageChart.vue)

```vue
<template>
  <div class="w-full h-64">
    <canvas ref="chartCanvas"></canvas>
  </div>
</template>

<script setup lang="ts">
import { Chart, registerables } from 'chart.js'
import type { DailyUsage } from '~/types/usage'

Chart.register(...registerables)

const props = defineProps<{
  data: DailyUsage[]
}>()

const chartCanvas = ref<HTMLCanvasElement | null>(null)
let chartInstance: Chart | null = null

onMounted(() => {
  if (chartCanvas.value) {
    createChart()
  }
})

watch(() => props.data, () => {
  if (chartInstance) {
    updateChart()
  }
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.destroy()
  }
})

function createChart() {
  if (!chartCanvas.value) return

  const labels = props.data.map(d => d.date)
  const tokens = props.data.map(d => d.tokens)
  const costs = props.data.map(d => d.cost)

  chartInstance = new Chart(chartCanvas.value, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Tokens',
          data: tokens,
          borderColor: 'rgb(99, 102, 241)',
          backgroundColor: 'rgba(99, 102, 241, 0.1)',
          yAxisID: 'y'
        },
        {
          label: 'Cost ($)',
          data: costs,
          borderColor: 'rgb(234, 179, 8)',
          backgroundColor: 'rgba(234, 179, 8, 0.1)',
          yAxisID: 'y1'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      scales: {
        y: {
          type: 'linear',
          display: true,
          position: 'left',
          title: {
            display: true,
            text: 'Tokens'
          }
        },
        y1: {
          type: 'linear',
          display: true,
          position: 'right',
          title: {
            display: true,
            text: 'Cost ($)'
          },
          grid: {
            drawOnChartArea: false
          }
        }
      }
    }
  })
}

function updateChart() {
  if (!chartInstance) return

  chartInstance.data.labels = props.data.map(d => d.date)
  chartInstance.data.datasets[0].data = props.data.map(d => d.tokens)
  chartInstance.data.datasets[1].data = props.data.map(d => d.cost)
  chartInstance.update()
}
</script>
```

### 7. Cost Breakdown Component (frontend/components/CostBreakdown.vue)

```vue
<template>
  <div class="bg-white rounded-lg shadow p-6">
    <h2 class="text-xl font-semibold mb-4">Cost Breakdown by Operation</h2>

    <div class="space-y-3">
      <div
        v-for="(data, operation) in summary.by_operation"
        :key="operation"
        class="flex items-center justify-between p-3 bg-gray-50 rounded"
      >
        <div class="flex-1">
          <div class="flex items-center space-x-2">
            <span class="font-medium capitalize">{{ operation.replace('_', ' ') }}</span>
            <span class="text-sm text-gray-500">{{ data.count }} operations</span>
          </div>

          <div class="mt-1">
            <div class="w-full bg-gray-200 rounded-full h-2">
              <div
                :style="{ width: `${getPercentage(data.cost)}%` }"
                class="bg-indigo-600 h-2 rounded-full"
              ></div>
            </div>
          </div>
        </div>

        <div class="ml-4 text-right">
          <div class="text-lg font-semibold">${{ data.cost.toFixed(4) }}</div>
          <div class="text-sm text-gray-500">{{ (data.tokens / 1000).toFixed(1) }}K tokens</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { UsageSummary } from '~/types/usage'

const props = defineProps<{
  summary: UsageSummary
}>()

function getPercentage(cost: number): number {
  const total = props.summary.totals.cost
  return total > 0 ? (cost / total) * 100 : 0
}
</script>
```

### 8. Update Navigation (frontend/components/Navbar.vue)

Add links to memory and usage pages:

```vue
<template>
  <nav class="bg-white shadow">
    <div class="container mx-auto px-4">
      <div class="flex justify-between items-center h-16">
        <div class="flex space-x-8">
          <NuxtLink to="/" class="text-gray-700 hover:text-indigo-600">Chat</NuxtLink>
          <NuxtLink to="/connections" class="text-gray-700 hover:text-indigo-600">Connections</NuxtLink>
          <NuxtLink to="/memory" class="text-gray-700 hover:text-indigo-600">Memory</NuxtLink>
          <NuxtLink to="/usage" class="text-gray-700 hover:text-indigo-600">Usage</NuxtLink>
        </div>

        <div v-if="user" class="flex items-center space-x-4">
          <span class="text-gray-700">{{ user.email }}</span>
          <button
            @click="handleLogout"
            class="text-gray-700 hover:text-indigo-600"
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
const auth = useAuth()
const user = computed(() => auth.user.value)

function handleLogout() {
  auth.logout()
}
</script>
```

## Testing & Verification

### Manual Testing Steps

1. **Test memory page**:
   - Navigate to /memory
   - Search for "users"
   - Verify memories displayed
   - Generate today's memory
   - Delete all memories

2. **Test usage dashboard**:
   - Navigate to /usage
   - Verify stats cards show correct totals
   - Change date range (7/30/90 days)
   - Verify chart updates
   - Verify cost breakdown displays

3. **Test dashboard navigation**:
   - Navigate between pages
   - Verify nav links work
   - Verify logout works

## MCP Browser Testing

```typescript
// Test memory page
await navigate_page({ url: 'http://localhost:3000/memory', type: 'url' })
await take_snapshot()

await fill({ uid: 'search-input', value: 'users' })
await click({ uid: 'search-button' })
await wait_for({ text: 'relevance' })
await take_snapshot()

// Test usage page
await navigate_page({ url: 'http://localhost:3000/usage', type: 'url' })
await take_snapshot()

// Verify charts rendered
await take_screenshot({ filePath: 'usage-dashboard.png' })

// Change date range
await click({ uid: 'days-select' })
await click({ uid: 'option-7' })
await wait_for({ text: 'Last 7 days' })
await take_snapshot()
```

## Code Review Checklist

- [ ] Memory search returns relevant results
- [ ] Usage charts update when date range changes
- [ ] Cost breakdown percentages correct
- [ ] Stats cards format numbers correctly (K for thousands)
- [ ] Memory generation shows feedback (alert or toast)
- [ ] Delete memories requires confirmation
- [ ] Charts responsive on mobile
- [ ] Navigation links styled consistently
- [ ] All pages require authentication

## Done Criteria

1. Memory page displays and searches memories
2. Usage dashboard shows stats, charts, and breakdown
3. Charts render correctly with Chart.js
4. Date range selector updates data
5. Navigation between pages works
6. All pages require authentication
7. Responsive on mobile devices
8. All MCP browser tests pass
9. Memory generation provides feedback
10. Cost breakdown shows all operation types

## Rollback Plan

If dashboard phase fails:
1. Memory and usage API still work via curl
2. Chat interface (Phase 10) remains functional
3. Connections UI (Phase 09) remains functional
4. Can revert dashboard pages without affecting backend

## MVP Completion

After Phase 11, the full MVP is complete:
- ✅ Authentication
- ✅ Database connections
- ✅ Natural language to SQL
- ✅ Query execution with results
- ✅ Data visualization
- ✅ Memory system
- ✅ Token tracking
- ✅ Full frontend UI

Ready for user testing and feedback!
