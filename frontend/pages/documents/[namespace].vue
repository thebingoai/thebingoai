<template>
  <div class="container mx-auto p-6">
    <!-- Header -->
    <div class="mb-6">
      <div class="mb-4 flex items-center gap-2 text-sm text-neutral-600 dark:text-neutral-400">
        <NuxtLink to="/documents" class="hover:text-brand-600 dark:hover:text-brand-400">
          Documents
        </NuxtLink>
        <component :is="ChevronRight" class="h-4 w-4" />
        <span class="text-neutral-900 dark:text-neutral-100">{{ namespace }}</span>
      </div>

      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
            {{ namespace }}
          </h1>
          <p class="mt-2 text-neutral-600 dark:text-neutral-400">
            {{ vectorCount }} vectors in this namespace
          </p>
        </div>
        <UiButton @click="showUploadModal = true">
          Upload to this namespace
        </UiButton>
      </div>
    </div>

    <!-- Content -->
    <div class="rounded-lg border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900">
      <UiEmptyState
        title="Document management coming soon"
        description="View and manage individual documents in this namespace"
        :icon="FileText"
      >
        <template #action>
          <UiButton variant="primary" @click="$router.push('/search')">
            Search in this namespace
          </UiButton>
        </template>
      </UiEmptyState>
    </div>

    <!-- Upload Modal -->
    <UploadModal
      v-model:open="showUploadModal"
      :namespaces="[namespace]"
      :default-namespace="namespace"
      @upload-complete="handleUploadComplete"
    />
  </div>
</template>

<script setup lang="ts">
import { ChevronRight, FileText } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const namespace = computed(() => route.params.namespace as string)

const { data: status, refresh } = useStatus()

const vectorCount = computed(() => {
  if (!status.value?.index?.namespaces) return 0
  return status.value.index.namespaces[namespace.value]?.vector_count || 0
})

const showUploadModal = ref(false)

const handleUploadComplete = () => {
  refresh()
}
</script>
