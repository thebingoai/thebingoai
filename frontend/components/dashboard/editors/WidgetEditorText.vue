<template>
  <div class="flex h-full">
    <!-- Left: form -->
    <div class="w-80 flex-shrink-0 border-r border-gray-100 overflow-y-auto p-5 space-y-5">
      <div class="space-y-1.5">
        <label class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Content (Markdown)</label>
        <textarea
          v-model="localContent"
          :readonly="!editMode"
          rows="12"
          class="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 font-mono text-xs text-gray-800 leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-colors"
          :class="editMode ? 'bg-white' : 'cursor-default'"
          spellcheck="false"
        />
      </div>

      <div class="space-y-1.5">
        <label class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Alignment</label>
        <div class="flex rounded-lg border border-gray-200 overflow-hidden">
          <button
            v-for="opt in alignOptions"
            :key="opt.value"
            class="flex-1 py-1.5 text-xs font-medium transition-colors"
            :class="localAlignment === opt.value
              ? 'bg-indigo-600 text-white'
              : 'bg-white text-gray-500 hover:bg-gray-50'"
            :disabled="!editMode"
            @click="editMode && (localAlignment = opt.value)"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- Right: live preview -->
    <div class="flex-1 overflow-hidden flex flex-col">
      <div class="px-4 py-2 border-b border-gray-100 flex-shrink-0">
        <span class="text-[11px] font-medium text-gray-400 uppercase tracking-wide">Preview</span>
      </div>
      <div class="flex-1 overflow-auto min-h-0">
        <DashboardWidgetText :config="previewConfig" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WidgetConfig, TextWidgetConfig } from '~/types/dashboard'

const props = defineProps<{
  modelValue: WidgetConfig
  editMode: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WidgetConfig]
}>()

const textConfig = computed(() => props.modelValue.config as TextWidgetConfig)

const localContent = computed({
  get: () => textConfig.value.content,
  set: (v) => emit('update:modelValue', { type: 'text', config: { ...textConfig.value, content: v } }),
})

const localAlignment = computed({
  get: () => textConfig.value.alignment ?? 'left',
  set: (v) => emit('update:modelValue', { type: 'text', config: { ...textConfig.value, alignment: v as TextWidgetConfig['alignment'] } }),
})

const previewConfig = computed(() => props.modelValue.config as TextWidgetConfig)

const alignOptions = [
  { value: 'left', label: 'Left' },
  { value: 'center', label: 'Center' },
  { value: 'right', label: 'Right' },
]
</script>
