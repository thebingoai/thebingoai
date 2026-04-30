<template>
  <div class="flex h-full flex-col p-3">
    <div v-if="config.title" class="mb-2 flex-shrink-0">
      <span class="widget-label">{{ config.title }}</span>
    </div>
    <div class="relative min-h-0 flex-1">
      <canvas ref="canvasRef" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChartWidgetConfig } from '~/types/dashboard'
import { useChart } from '~/composables/useChart'

const props = defineProps<{
  config: ChartWidgetConfig
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const configRef = computed(() => props.config)

useChart(canvasRef, configRef)
</script>
