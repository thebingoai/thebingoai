<template>
  <div class="w-full">
    <div v-if="label" class="mb-2 flex items-center justify-between text-sm">
      <span class="font-medium text-neutral-700 dark:text-neutral-300">{{ label }}</span>
      <span v-if="showPercentage" class="text-neutral-500 dark:text-neutral-400">{{ value }}%</span>
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
  default: 'bg-brand-600 dark:bg-brand-500',
  success: 'bg-success-600 dark:bg-success-500',
  warning: 'bg-warning-600 dark:bg-warning-500',
  error: 'bg-error-600 dark:bg-error-500'
}

const trackClasses = computed(() =>
  cn(
    'w-full overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800',
    sizeClasses[props.size]
  )
)

const barClasses = computed(() =>
  cn(
    'h-full rounded-full transition-all',
    variantClasses[props.variant],
    props.animated && 'transition-all duration-300 ease-in-out'
  )
)
</script>
