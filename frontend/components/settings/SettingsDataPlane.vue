<template>
  <div class="flex flex-col h-full overflow-hidden">

    <!-- Page header -->
    <div class="px-7 pt-3 pb-2 border-b border-[var(--line)] flex-shrink-0">
      <p class="eyebrow mb-0.5 text-gray-400 dark:text-neutral-500">Settings · Storage</p>
      <h1 class="settings-h1 text-3xl text-gray-900 dark:text-neutral-100 mb-1">Data Plane</h1>
    </div>

    <!-- Scrolling body -->
    <div class="flex-1 overflow-y-auto px-7 py-6 space-y-6">
      <p class="text-sm text-gray-500 dark:text-neutral-400 max-w-2xl">
        Configure where Bingo stores materialized dashboard data.
        Choose <strong>Local Filesystem</strong> for self-hosted or dev, or
        <strong>Google Cloud Project</strong> for cloud production.
      </p>

    <!-- Loading -->
    <div v-if="loading" class="space-y-3">
      <UiSkeleton class="h-20 w-full rounded-lg" />
      <UiSkeleton class="h-20 w-full rounded-lg" />
    </div>

    <template v-else>
      <!-- Existing planes -->
      <div v-if="planes.length" class="space-y-3 mb-6">
        <div
          v-for="plane in planes"
          :key="plane.id"
          class="flex items-start justify-between rounded-lg border p-4"
          :class="plane.is_default ? 'border-blue-500 bg-blue-50' : 'border-gray-200'"
        >
          <div>
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-gray-900">{{ planeLabel(plane.type) }}</span>
              <UiBadge v-if="plane.is_default" variant="info" size="sm">Default</UiBadge>
            </div>
            <p class="mt-1 text-xs text-gray-500">{{ planeSummary(plane) }}</p>
          </div>
          <div class="flex gap-2 shrink-0 ml-4">
            <UiButton
              v-if="!plane.is_default"
              size="sm"
              variant="outline"
              @click="handleSetDefault(plane.id)"
            >
              Set default
            </UiButton>
            <UiButton
              size="sm"
              variant="ghost"
              class="text-red-500 hover:text-red-700"
              @click="handleDelete(plane.id)"
            >
              Remove
            </UiButton>
          </div>
        </div>
      </div>

      <UiEmptyState
        v-else
        title="No data planes configured"
        description="Add a data plane to enable Parquet-based dashboard caching."
        class="mb-6"
      />

      <!-- Add new plane -->
      <div class="rounded-lg border border-dashed border-gray-300 p-5">
        <h3 class="text-sm font-medium text-gray-900 mb-4">Add Data Plane</h3>
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-1">Type</label>
          <select
            v-model="newType"
            class="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="local_filesystem">Local Filesystem (dev / self-hosted)</option>
            <option value="google_cloud_project">Google Cloud Project (cloud production)</option>
          </select>
        </div>

        <LocalFilesystemForm
          v-if="newType === 'local_filesystem'"
          v-model="newConfig"
        />
        <BigQueryGCSForm
          v-else-if="newType === 'google_cloud_project'"
          v-model="newConfig"
          @update:credentials="newCredentials = $event"
        />

        <div class="mt-4 flex items-center gap-3">
          <label class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input v-model="newIsDefault" type="checkbox" class="rounded" />
            Set as default
          </label>
          <UiButton size="sm" :loading="saving" @click="handleCreate">
            Add Data Plane
          </UiButton>
        </div>

        <p v-if="saveError" class="mt-2 text-xs text-red-600">{{ saveError }}</p>
      </div>
    </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDataPlanes } from '../../composables/useDataPlanes'
import LocalFilesystemForm from './data_plane_forms/LocalFilesystemForm.vue'
import BigQueryGCSForm from './data_plane_forms/BigQueryGCSForm.vue'

const props = defineProps<{
  orgId: string
}>()

const { planes, loading, error, fetchPlanes, createPlane, deletePlane, setDefault } = useDataPlanes()

const newType = ref<'local_filesystem' | 'google_cloud_project'>('local_filesystem')
const newConfig = ref<Record<string, unknown>>({})
const newCredentials = ref('')
const newIsDefault = ref(false)
const saving = ref(false)
const saveError = ref<string | null>(null)

onMounted(() => fetchPlanes(props.orgId))

function planeLabel(type: string): string {
  return type === 'local_filesystem' ? 'Local Filesystem' : 'Google Cloud Project'
}

function planeSummary(plane: { type: string; config: Record<string, unknown> }): string {
  if (plane.type === 'local_filesystem') {
    return `Root: ${plane.config.root_path ?? '/data/data_plane'}`
  }
  return `Project: ${plane.config.gcp_project ?? '—'} · Bucket: ${plane.config.gcs_bucket ?? '—'}`
}

async function handleCreate() {
  saveError.value = null
  saving.value = true
  try {
    await createPlane({
      owner_scope_kind: 'org',
      owner_scope_id: props.orgId,
      type: newType.value,
      config: newConfig.value,
      credentials: newCredentials.value || undefined,
      is_default: newIsDefault.value,
    })
    newConfig.value = {}
    newCredentials.value = ''
    newIsDefault.value = false
  } catch (e: unknown) {
    saveError.value = e instanceof Error ? e.message : 'Failed to create data plane'
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: string) {
  await deletePlane(id)
}

async function handleSetDefault(id: string) {
  await setDefault(id)
}
</script>
