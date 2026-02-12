<template>
  <div class="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
    <div class="mb-4 flex items-center justify-between">
      <h3 class="font-semibold text-neutral-900 dark:text-neutral-100">
        Filters
      </h3>
      <button
        @click="$emit('reset')"
        class="text-sm text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
      >
        Reset
      </button>
    </div>

    <div class="space-y-4">
      <!-- Top K Slider -->
      <div>
        <label class="mb-2 block text-sm font-medium text-neutral-700 dark:text-neutral-300">
          Results: {{ topK }}
        </label>
        <input
          :value="topK"
          type="range"
          min="1"
          max="20"
          @input="$emit('update:topK', parseInt(($event.target as HTMLInputElement).value))"
          class="w-full"
        />
        <div class="mt-1 flex justify-between text-xs text-neutral-500">
          <span>1</span>
          <span>20</span>
        </div>
      </div>

      <!-- Min Score Slider -->
      <div>
        <label class="mb-2 block text-sm font-medium text-neutral-700 dark:text-neutral-300">
          Min Score: {{ minScore.toFixed(2) }}
        </label>
        <input
          :value="minScore"
          type="range"
          min="0"
          max="1"
          step="0.05"
          @input="$emit('update:minScore', parseFloat(($event.target as HTMLInputElement).value))"
          class="w-full"
        />
        <div class="mt-1 flex justify-between text-xs text-neutral-500">
          <span>0.0</span>
          <span>1.0</span>
        </div>
      </div>

      <!-- Namespaces -->
      <div>
        <label class="mb-2 block text-sm font-medium text-neutral-700 dark:text-neutral-300">
          Namespaces
        </label>
        <div class="space-y-2">
          <label
            v-for="namespace in availableNamespaces"
            :key="namespace"
            class="flex items-center gap-2"
          >
            <input
              type="checkbox"
              :checked="selectedNamespaces.includes(namespace)"
              @change="toggleNamespace(namespace)"
              class="h-4 w-4 rounded border-neutral-300 text-brand-600 focus:ring-brand-500 dark:border-neutral-700"
            />
            <span class="text-sm text-neutral-700 dark:text-neutral-300">
              {{ namespace }}
            </span>
          </label>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  topK: number
  minScore: number
  selectedNamespaces: string[]
  availableNamespaces: string[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:topK': [value: number]
  'update:minScore': [value: number]
  'update:selectedNamespaces': [value: string[]]
  reset: []
}>()

const toggleNamespace = (namespace: string) => {
  const newSelection = [...props.selectedNamespaces]
  const index = newSelection.indexOf(namespace)

  if (index > -1) {
    newSelection.splice(index, 1)
  } else {
    newSelection.push(namespace)
  }

  emit('update:selectedNamespaces', newSelection)
}
</script>
