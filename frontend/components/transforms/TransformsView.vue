<template>
  <TransformDetailView v-if="detailId" :id="detailId" @back="closeDetail" />

  <div v-else class="p-4 md:p-6">
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-medium text-gray-900 dark:text-neutral-100">Transforms</h1>
        <p class="mt-1 text-sm text-gray-500 dark:text-neutral-400">
          Define SQL models that join and aggregate your pipeline data.
        </p>
      </div>
      <UiButton @click="showCreateModal = true">
        <Plus class="h-4 w-4" />
        New Transform
      </UiButton>
    </div>

    <!-- Loading skeletons -->
    <div v-if="loading" class="space-y-3">
      <UiSkeleton class="h-24 w-full rounded-lg" />
      <UiSkeleton class="h-24 w-full rounded-lg" />
      <UiSkeleton class="h-24 w-full rounded-lg" />
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-400"
    >
      {{ error }}
    </div>

    <!-- Empty state -->
    <UiEmptyState
      v-else-if="transforms.length === 0"
      title="No transforms yet"
      description="Create a transform to define SQL models that aggregate your pipeline data."
      :icon="GitBranch"
    >
      <template #action>
        <UiButton @click="showCreateModal = true">
          Create Your First Transform
        </UiButton>
      </template>
    </UiEmptyState>

    <!-- Transform list -->
    <div v-else class="space-y-3">
      <UiCard
        v-for="transform in transforms"
        :key="transform.id"
        class="px-5 py-4 cursor-pointer hover:shadow-lg transition-shadow"
        @click="openDetail(transform.id)"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-sm font-medium text-gray-900 dark:text-neutral-100 truncate">
                {{ transform.name }}
              </span>
              <UiBadge :variant="statusVariant(transform.last_run_status)" size="sm" :dot="true">
                {{ statusLabel(transform.last_run_status) }}
              </UiBadge>
              <UiBadge variant="default" size="sm" class="capitalize">{{ transform.materialization }}</UiBadge>
              <UiBadge v-if="!transform.enabled" variant="warning" size="sm">Disabled</UiBadge>
            </div>

            <div class="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-neutral-400">
              <span v-if="transform.cron" class="flex items-center gap-1">
                <Clock class="h-3 w-3" />
                {{ transform.cron }}
              </span>
              <span v-else class="flex items-center gap-1 italic">
                <Clock class="h-3 w-3" />
                Manual only
              </span>
            </div>

            <div v-if="transform.last_run_at" class="mt-1 text-xs text-gray-400 dark:text-neutral-500">
              Last run {{ formatRelative(transform.last_run_at) }}
              <template v-if="transform.next_run_at">
                · Next {{ formatRelative(transform.next_run_at) }}
              </template>
            </div>
          </div>

          <div class="shrink-0 flex items-center gap-2">
            <UiButton
              size="sm"
              variant="outline"
              :loading="runningTransforms.has(transform.id)"
              :disabled="runningTransforms.has(transform.id)"
              @click.stop="handleRun(transform.id)"
            >
              <Play class="h-3.5 w-3.5" />
              Run
            </UiButton>
          </div>
        </div>
      </UiCard>
    </div>

    <!-- Create modal -->
    <TransformsTransformEditor
      :open="showCreateModal"
      @update:open="showCreateModal = $event"
      @created="handleCreated"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Plus, Play, Clock, GitBranch } from 'lucide-vue-next'
import { useUserTransforms } from '~/composables/useUserTransforms'

const route = useRoute()
const router = useRouter()

const detailId = computed(() => (route.query.id as string) || '')

function openDetail(id: string) {
  router.push({ query: { ...route.query, id } })
}

function closeDetail() {
  const next = { ...route.query }
  delete next.id
  router.replace({ query: next })
}

const { transforms, loading, error, fetchTransforms, triggerRun } = useUserTransforms()
const showCreateModal = ref(false)
const runningTransforms = ref<Set<string>>(new Set())

onMounted(() => fetchTransforms())

async function handleRun(transformId: string) {
  runningTransforms.value = new Set([...runningTransforms.value, transformId])
  try {
    await triggerRun(transformId)
    await fetchTransforms()
  } finally {
    const next = new Set(runningTransforms.value)
    next.delete(transformId)
    runningTransforms.value = next
  }
}

function handleCreated() {
  showCreateModal.value = false
  fetchTransforms()
}

function statusVariant(status: string | null): 'success' | 'error' | 'info' | 'default' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'running') return 'info'
  return 'default'
}

function statusLabel(status: string | null): string {
  if (status === 'success') return 'Success'
  if (status === 'failed') return 'Failed'
  if (status === 'running') return 'Running'
  return 'Never run'
}

function formatRelative(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.round(diffMs / 1000)
  if (diffSec < 60) return 'just now'
  const diffMin = Math.round(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.round(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.round(diffHr / 24)
  if (diffDay < 30) return `${diffDay}d ago`
  return date.toLocaleDateString()
}
</script>
