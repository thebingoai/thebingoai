<template>
  <div class="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md dark:border-neutral-800 dark:bg-neutral-900">
    <div class="flex items-center justify-between">
      <div class="flex-1">
        <p class="text-sm font-medium text-neutral-600 dark:text-neutral-400">
          {{ label }}
        </p>
        <p class="mt-2 text-3xl font-semibold text-neutral-900 dark:text-neutral-100">
          {{ loading ? '—' : formattedValue }}
        </p>
        <p v-if="change !== undefined" class="mt-2 flex items-center gap-1 text-sm" :class="changeColor">
          <component :is="changeIcon" class="h-4 w-4" />
          <span>{{ change }}% from last month</span>
        </p>
      </div>
      <div class="rounded-full p-3" :class="iconBgClass">
        <component :is="icon" class="h-6 w-6" :class="iconClass" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { TrendingUp, TrendingDown } from 'lucide-vue-next'

interface Props {
  label: string
  value: number | string
  icon: Component
  change?: number
  loading?: boolean
  variant?: 'default' | 'primary' | 'success' | 'warning'
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  variant: 'default'
})

const formattedValue = computed(() => {
  if (typeof props.value === 'number') {
    return props.value.toLocaleString()
  }
  return props.value
})

const changeIcon = computed(() => {
  if (props.change === undefined) return null
  return props.change >= 0 ? TrendingUp : TrendingDown
})

const changeColor = computed(() => {
  if (props.change === undefined) return ''
  return props.change >= 0
    ? 'text-success-600 dark:text-success-400'
    : 'text-error-600 dark:text-error-400'
})

const variantClasses = {
  default: {
    bg: 'bg-neutral-100 dark:bg-neutral-800',
    icon: 'text-neutral-600 dark:text-neutral-400'
  },
  primary: {
    bg: 'bg-brand-100 dark:bg-brand-900/20',
    icon: 'text-brand-600 dark:text-brand-400'
  },
  success: {
    bg: 'bg-success-100 dark:bg-success-900/20',
    icon: 'text-success-600 dark:text-success-400'
  },
  warning: {
    bg: 'bg-warning-100 dark:bg-warning-900/20',
    icon: 'text-warning-600 dark:text-warning-400'
  }
}

const iconBgClass = computed(() => variantClasses[props.variant].bg)
const iconClass = computed(() => variantClasses[props.variant].icon)
</script>
