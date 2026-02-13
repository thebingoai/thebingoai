<template>
  <div class="group relative inline-block">
    <slot />
    <div
      v-if="content"
      :class="tooltipClasses"
    >
      {{ content }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { cn } from '~/utils/cn'

interface Props {
  content?: string
  position?: 'top' | 'bottom' | 'left' | 'right'
}

const props = withDefaults(defineProps<Props>(), {
  position: 'top'
})

const positionClasses = {
  top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
  bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
  left: 'right-full top-1/2 -translate-y-1/2 mr-2',
  right: 'left-full top-1/2 -translate-y-1/2 ml-2'
}

const tooltipClasses = computed(() =>
  cn(
    'pointer-events-none absolute z-50 whitespace-nowrap rounded-lg bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 dark:bg-neutral-700',
    positionClasses[props.position]
  )
)
</script>
