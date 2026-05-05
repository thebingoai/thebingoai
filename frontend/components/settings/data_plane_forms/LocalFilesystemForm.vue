<template>
  <div class="space-y-4">
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">Root Path</label>
      <input
        v-model="form.root_path"
        type="text"
        placeholder="/data/data_plane"
        class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <p class="mt-1 text-xs text-gray-500">Docker volume path or local directory for Parquet files.</p>
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
  root_path: (props.modelValue?.root_path as string) ?? '/data/data_plane',
})

watch(form, () => {
  emit('update:modelValue', { root_path: form.root_path })
})
</script>
