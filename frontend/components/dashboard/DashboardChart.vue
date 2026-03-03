<template>
  <div ref="containerRef" class="flex flex-col rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
    <div v-if="config.title" class="mb-3 flex items-start justify-between">
      <div>
        <h3 class="text-sm font-medium text-gray-800">{{ config.title }}</h3>
        <p v-if="config.description" class="mt-0.5 text-xs text-gray-400">{{ config.description }}</p>
      </div>
    </div>
    <div class="relative min-h-0 flex-1">
      <canvas ref="canvasRef" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChartConfig } from '~/types/chart'
import { useChart } from '~/composables/useChart'
import { useChartAnimation } from '~/composables/useChartAnimation'

const props = defineProps<{
  config: ChartConfig
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLElement | null>(null)
const configRef = computed(() => props.config)

useChart(canvasRef, configRef)
useChartAnimation(containerRef, props.config.animation)
</script>
