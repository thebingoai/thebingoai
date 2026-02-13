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

const baseClasses = 'inline-flex items-center gap-1.5 rounded-full font-light'

const variantClasses = {
  default: 'bg-gray-100 text-gray-700',
  primary: 'bg-gray-900 text-white',
  success: 'bg-green-100 text-green-700',
  warning: 'bg-yellow-100 text-yellow-700',
  error: 'bg-red-100 text-red-700',
  info: 'bg-blue-100 text-blue-700'
}

const sizeClasses = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-sm',
  lg: 'px-3 py-1.5 text-base'
}

const dotColorClasses = computed(() => {
  const colors = {
    default: 'bg-gray-500',
    primary: 'bg-gray-900',
    success: 'bg-green-500',
    warning: 'bg-yellow-500',
    error: 'bg-red-500',
    info: 'bg-blue-500'
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
