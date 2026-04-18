<template>
  <div class="w-full">
    <div v-if="label" class="mb-2 flex items-center justify-between text-sm">
      <span class="font-light text-gray-700 dark:text-neutral-300">{{ label }}</span>
      <span v-if="showPercentage" class="text-gray-500 dark:text-neutral-500">{{ value }}%</span>
    </div>
    <div :class="trackClasses">
      <div
        :class="barClasses"
        :style="{ width: `${clampedValue}%` }"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { cn } from '~/utils/cn'

interface Props {
  value: number
  label?: string
  showPercentage?: boolean
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'success' | 'warning' | 'error'
  animated?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showPercentage: true,
  size: 'md',
  variant: 'default',
  animated: false
})

const clampedValue = computed(() => Math.min(Math.max(props.value, 0), 100))

const sizeClasses = {
  sm: 'h-1.5',
  md: 'h-2.5',
  lg: 'h-3.5'
}

const variantClasses = {
  default: 'bg-gray-900',
  success: 'bg-green-600',
  warning: 'bg-yellow-600',
  error: 'bg-red-600'
}

const trackClasses = computed(() =>
  cn(
    'w-full overflow-hidden rounded-full bg-gray-200 dark:bg-neutral-700',
    sizeClasses[props.size]
  )
)

const barClasses = computed(() =>
  cn(
    'h-full rounded-full',
    variantClasses[props.variant]
  )
)
</script>
