<template>
  <div class="container mx-auto p-6">
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
          Documents
        </h1>
        <p class="mt-2 text-neutral-600 dark:text-neutral-400">
          Manage your markdown documents and namespaces
        </p>
      </div>
      <UiButton @click="showUploadModal = true" :icon="Upload">
        Upload Documents
      </UiButton>
    </div>

    <!-- Main Content -->
    <div class="grid gap-6 lg:grid-cols-4">
      <!-- Namespace Sidebar -->
      <div class="lg:col-span-1">
        <NamespaceTree
          :namespaces="namespaces"
          :loading="statusPending"
        />
      </div>

      <!-- Documents List -->
      <div class="lg:col-span-3">
        <div class="rounded-lg border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900">
          <UiEmptyState
            title="Select a namespace"
            description="Choose a namespace from the sidebar to view its documents"
            :icon="FolderOpen"
          />
        </div>
      </div>
    </div>

    <!-- Upload Modal -->
    <UploadModal
      v-model:open="showUploadModal"
      :namespaces="namespaceNames"
      :default-namespace="settings.defaultNamespace"
      @upload-complete="handleUploadComplete"
    />
  </div>
</template>

<script setup lang="ts">
import { Upload, FolderOpen } from 'lucide-vue-next'

const settings = useSettingsStore()
const { data: status, pending: statusPending, refresh } = useStatus()
const { namespaces, namespaceNames } = useNamespaces()

const showUploadModal = ref(false)

const handleUploadComplete = () => {
  // Refresh status to update namespace counts
  refresh()
}
</script>
