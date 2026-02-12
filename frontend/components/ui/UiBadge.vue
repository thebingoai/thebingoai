<template>
  <span :class="badgeClasses">
    <span v-if="dot" class="h-1.5 w-1.5 rounded-full" :class="dotColorClasses" />
    <slot />
  </span>
</template>

<script setup lang="ts">
import { cn } from '~/utils/cn'

interface Props {
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'error' | 'info'
  size?: 'sm' | 'md' | 'lg'
  dot?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  size: 'md',
  dot: false
})

const baseClasses = 'inline-flex items-center gap-1.5 rounded-full font-medium'

const variantClasses = {
  default: 'bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300',
  primary: 'bg-brand-100 text-brand-700 dark:bg-brand-900/20 dark:text-brand-400',
  success: 'bg-success-100 text-success-700 dark:bg-success-900/20 dark:text-success-400',
  warning: 'bg-warning-100 text-warning-700 dark:bg-warning-900/20 dark:text-warning-400',
  error: 'bg-error-100 text-error-700 dark:bg-error-900/20 dark:text-error-400',
  info: 'bg-info-100 text-info-700 dark:bg-info-900/20 dark:text-info-400'
}

const sizeClasses = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-sm',
  lg: 'px-3 py-1.5 text-base'
}

const dotColorClasses = computed(() => {
  const colors = {
    default: 'bg-neutral-500',
    primary: 'bg-brand-500',
    success: 'bg-success-500',
    warning: 'bg-warning-500',
    error: 'bg-error-500',
    info: 'bg-info-500'
  }
  return colors[props.variant]
})

const badgeClasses = computed(() =>
  cn(
    baseClasses,
    variantClasses[props.variant],
    sizeClasses[props.size]
  )
)
</script>
