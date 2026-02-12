<template>
  <div class="container mx-auto p-6">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
        Dashboard
      </h1>
      <p class="mt-2 text-neutral-600 dark:text-neutral-400">
        Overview of your LLM-MD-CLI system
      </p>
    </div>

    <!-- Stats Grid -->
    <div class="mb-8 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
      <StatCard
        label="Documents"
        :value="totalDocuments"
        :icon="FileText"
        :loading="statusPending"
        variant="primary"
      />
      <StatCard
        label="Vectors"
        :value="totalVectors"
        :icon="Database"
        :loading="statusPending"
        variant="success"
      />
      <StatCard
        label="Namespaces"
        :value="totalNamespaces"
        :icon="FolderOpen"
        :loading="statusPending"
        variant="warning"
      />
      <StatCard
        label="Queries (Today)"
        :value="0"
        :icon="Search"
        variant="default"
      />
    </div>

    <!-- Quick Actions -->
    <div class="mb-8">
      <h2 class="mb-4 text-xl font-semibold text-neutral-900 dark:text-neutral-100">
        Quick Actions
      </h2>
      <div class="grid gap-4 md:grid-cols-2">
        <QuickActionCard
          title="Upload Documents"
          description="Add new markdown files to your knowledge base"
          :icon="Upload"
          to="/documents"
        />
        <QuickActionCard
          title="Start a Chat"
          description="Ask questions about your documents"
          :icon="MessageSquare"
          to="/chat"
        />
      </div>
    </div>

    <!-- Activity & System Status -->
    <div class="grid gap-6 lg:grid-cols-2">
      <ActivityList :activities="recentActivities" :loading="false" />
      <SystemStatus :health="health" :loading="healthPending" />
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  FileText,
  Database,
  FolderOpen,
  Search,
  Upload,
  MessageSquare
} from 'lucide-vue-next'
import type { Activity } from '~/types'

// Fetch data
const { data: status, pending: statusPending } = useStatus()
const { data: health, pending: healthPending } = useDetailedHealth()
const settings = useSettingsStore()

// Computed stats
const totalVectors = computed(() => status.value?.index?.total_vectors || 0)
const totalNamespaces = computed(() => {
  if (!status.value?.index?.namespaces) return 0
  return Object.keys(status.value.index.namespaces).length
})
const totalDocuments = computed(() => {
  // Estimate documents (rough approximation)
  return Math.ceil((totalVectors.value || 0) / 10)
})

// Mock recent activities (in a real app, this would come from a store or API)
const recentActivities = ref<Activity[]>([
  {
    id: '1',
    type: 'upload_complete',
    description: 'Uploaded README.md to default namespace',
    timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString()
  }
])

// Update connection status based on health check
watch(health, (newHealth) => {
  if (newHealth) {
    const status: 'connected' | 'disconnected' | 'checking' =
      newHealth.status === 'healthy' ? 'connected' : 'disconnected'
    settings.setConnectionStatus(status)
  }
}, { immediate: true })

// Refresh data on mount
onMounted(() => {
  const { refresh: refreshStatus } = useStatus()
  const { refresh: refreshHealth } = useDetailedHealth()

  refreshStatus()
  refreshHealth()
})
</script>
