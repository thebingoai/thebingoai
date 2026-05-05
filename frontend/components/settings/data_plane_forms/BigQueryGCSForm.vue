<template>
  <div class="space-y-4">
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">GCP Project ID</label>
      <input
        v-model="form.gcp_project"
        type="text"
        placeholder="my-gcp-project"
        class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">GCS Bucket</label>
      <input
        v-model="form.gcs_bucket"
        type="text"
        placeholder="my-bingo-data-bucket"
        class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <p class="mt-1 text-xs text-gray-500">Bucket name only — without the gs:// prefix.</p>
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">BigQuery Dataset</label>
      <input
        v-model="form.bq_dataset"
        type="text"
        placeholder="bingo_dataplane"
        class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <p class="mt-1 text-xs text-gray-500">BigQuery dataset where external Parquet tables will be registered.</p>
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">Service Account JSON</label>
      <textarea
        v-model="form.service_account_json"
        rows="6"
        placeholder='{"type": "service_account", "project_id": "...", ...}'
        class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <p class="mt-1 text-xs text-gray-500">Paste the full JSON key file. Stored encrypted at rest.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'

const props = defineProps<{
  modelValue?: Record<string, unknown>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: Record<string, unknown>): void
  (e: 'update:credentials', value: string): void
}>()

const form = reactive({
  gcp_project: (props.modelValue?.gcp_project as string) ?? '',
  gcs_bucket: (props.modelValue?.gcs_bucket as string) ?? '',
  bq_dataset: (props.modelValue?.bq_dataset as string) ?? 'bingo_dataplane',
  service_account_json: '',
})

watch(
  () => ({ ...form }),
  () => {
    emit('update:modelValue', {
      gcp_project: form.gcp_project,
      gcs_bucket: form.gcs_bucket,
      bq_dataset: form.bq_dataset,
    })
    if (form.service_account_json) {
      emit('update:credentials', form.service_account_json)
    }
  },
)
</script>
