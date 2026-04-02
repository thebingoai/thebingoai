<template>
  <div class="h-full overflow-hidden" :class="[alignClass, editMode ? 'px-3 py-1 compact-text' : 'p-4']">
    <UiMarkdownRenderer :content="config.content" />
  </div>
</template>

<script setup lang="ts">
import type { TextWidgetConfig } from '~/types/dashboard'

const props = defineProps<{
  config: TextWidgetConfig
  editMode?: boolean
}>()

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
