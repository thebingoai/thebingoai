<template>
  <div ref="wrapperRef" :class="[alignClass, editMode ? 'px-3 py-1 compact-text' : 'p-4']">
    <UiMarkdownRenderer :content="config.content" />
  </div>
</template>

<script setup lang="ts">
import type { TextWidgetConfig } from '~/types/dashboard'

const props = defineProps<{
  widgetId: string
  config: TextWidgetConfig
  editMode?: boolean
}>()

const wrapperRef = ref<HTMLElement | null>(null)
const resizeWidget = inject<(id: string, h: number) => void>('resizeWidget')

// GridStack init constants — must match useDashboardGrid.ts
const CELL_HEIGHT = 70
const MARGIN = 4
const INSET = 4

function autoResize() {
  if (!wrapperRef.value || !resizeWidget) return
  const scrollH = wrapperRef.value.scrollHeight
  // overhead: inset*2 + one margin gap + pt-7 in edit mode
  const overhead = (INSET * 2 + MARGIN) + (props.editMode ? 28 : 0)
  const neededH = Math.max(2, Math.ceil((scrollH + overhead) / (CELL_HEIGHT + MARGIN)))
  resizeWidget(props.widgetId, neededH)
}

onMounted(() => nextTick(autoResize))
watch(() => props.config.content, () => nextTick(autoResize))

const alignClass = computed(() => {
  switch (props.config.alignment) {
    case 'center': return 'text-center'
    case 'right': return 'text-right'
    default: return 'text-left'
  }
})
</script>

<style scoped>
.compact-text :deep(h1),
.compact-text :deep(h2),
.compact-text :deep(h3),
.compact-text :deep(h4) {
  margin-top: 0;
  margin-bottom: 0;
}
</style>
