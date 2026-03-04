<template>
  <!-- Backdrop -->
  <div
    class="panel-backdrop fixed inset-0 z-40 bg-black/20 backdrop-blur-[2px]"
    @click="emit('close')"
  />

  <!-- Side panel -->
  <div class="panel-slide fixed right-0 top-0 z-50 flex h-full w-[720px] max-w-[90vw] flex-col bg-white shadow-2xl">

    <!-- Header -->
    <div class="flex flex-shrink-0 items-center gap-3 border-b border-gray-100 px-5 py-3.5">
      <button
        class="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
        @click="emit('close')"
      >
        <X class="h-4 w-4" />
      </button>
      <div class="min-w-0">
        <h2 class="text-sm font-semibold text-gray-900">Edit Widget</h2>
        <p class="text-[11px] text-gray-400">{{ widgetTypeLabel }}</p>
      </div>
      <!-- Save action in header for quick access -->
      <div class="ml-auto flex items-center gap-2">
        <span v-if="!editMode" class="text-[11px] text-gray-400">View only</span>
        <button
          v-if="editMode"
          class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium bg-indigo-600 text-white hover:bg-indigo-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          :disabled="!hasChanges"
          @click="save()"
        >
          <Save class="h-3.5 w-3.5" />
          Save
        </button>
      </div>
    </div>

    <!-- Common meta fields -->
    <div class="flex flex-shrink-0 gap-4 border-b border-gray-100 bg-gray-50 px-5 py-3">
      <div class="flex-1 space-y-1">
        <label class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Title</label>
        <input
          v-model="localTitle"
          type="text"
          placeholder="Widget title (optional)"
          class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-colors"
          :readonly="!editMode"
          :class="!editMode ? 'cursor-default bg-gray-50' : ''"
        />
      </div>
      <div class="flex-1 space-y-1">
        <label class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Description</label>
        <input
          v-model="localDescription"
          type="text"
          placeholder="Widget description (optional)"
          class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-colors"
          :readonly="!editMode"
          :class="!editMode ? 'cursor-default bg-gray-50' : ''"
        />
      </div>
    </div>

    <!-- Type-specific editor body -->
    <div class="min-h-0 flex-1 overflow-hidden">
      <component
        :is="editorComponent"
        v-if="editorComponent"
        v-model="localConfig"
        :edit-mode="editMode"
        class="h-full"
      />
      <div v-else class="flex h-full items-center justify-center p-10 text-sm text-gray-400">
        Configuration editor not yet available for this widget type.
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel-slide {
  animation: slideInRight 280ms cubic-bezier(0.16, 1, 0.3, 1);
}

.panel-backdrop {
  animation: fadeIn 200ms ease-out;
}

@keyframes slideInRight {
  from { transform: translateX(100%); }
  to   { transform: translateX(0); }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .panel-slide,
  .panel-backdrop { animation: none; }
}
</style>

<script lang="ts">
import { defineAsyncComponent } from 'vue'

// Defined at module level so they're singletons, not re-created on each setup call
const editorComponents: Record<string, ReturnType<typeof defineAsyncComponent>> = {
  text: defineAsyncComponent(() => import('./WidgetEditorText.vue')),
  kpi: defineAsyncComponent(() => import('./WidgetEditorKpi.vue')),
  table: defineAsyncComponent(() => import('./WidgetEditorTable.vue')),
  chart: defineAsyncComponent(() => import('./WidgetEditorChart.vue')),
}
</script>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { X, Save } from 'lucide-vue-next'
import type { DashboardWidget, WidgetConfig } from '~/types/dashboard'
import { useDashboardStore } from '~/stores/dashboard'

const props = defineProps<{
  widget: DashboardWidget
  editMode: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const store = useDashboardStore()

// Deep clone via JSON to safely copy reactive proxy data
const localConfig = ref<WidgetConfig>(JSON.parse(JSON.stringify(props.widget.widget)))
const localTitle = ref(props.widget.title ?? '')
const localDescription = ref(props.widget.description ?? '')

const WIDGET_TYPE_LABELS: Record<string, string> = {
  kpi: 'Score Chart',
  chart: 'Chart',
  table: 'Table',
  text: 'Text',
  filter: 'Filter',
}

const widgetTypeLabel = computed(() =>
  WIDGET_TYPE_LABELS[props.widget.widget.type] ?? props.widget.widget.type,
)

const editorComponent = computed(() =>
  editorComponents[props.widget.widget.type] ?? null,
)

const hasChanges = computed(() => {
  const configChanged = JSON.stringify(localConfig.value) !== JSON.stringify(props.widget.widget)
  const titleChanged = localTitle.value !== (props.widget.title ?? '')
  const descChanged = localDescription.value !== (props.widget.description ?? '')
  return configChanged || titleChanged || descChanged
})

function save() {
  store.updateWidgetConfig(props.widget.id, localConfig.value)
  store.updateWidgetMeta(props.widget.id, {
    title: localTitle.value || undefined,
    description: localDescription.value || undefined,
  })
  emit('close')
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>
