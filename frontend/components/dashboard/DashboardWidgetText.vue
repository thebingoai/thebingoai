<template>
  <div class="h-full overflow-auto p-4" :class="alignClass">
    <UiMarkdownRenderer :content="config.content" />
  </div>
</template>

<script setup lang="ts">
import type { TextWidgetConfig } from '~/types/dashboard'

const props = defineProps<{
  config: TextWidgetConfig
}>()

const alignClass = computed(() => {
  switch (props.config.alignment) {
    case 'center': return 'text-center'
    case 'right': return 'text-right'
    default: return 'text-left'
  }
})
</script>
