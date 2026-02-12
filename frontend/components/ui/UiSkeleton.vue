<template>
  <div :class="skeletonClasses" />
</template>

<script setup lang="ts">
import { cn } from '~/utils/cn'

interface Props {
  width?: string
  height?: string
  circle?: boolean
  className?: string
}

const props = defineProps<Props>()

const skeletonClasses = computed(() =>
  cn(
    'skeleton rounded-lg',
    props.circle && 'rounded-full',
    props.className
  )
)

const style = computed(() => ({
  width: props.width,
  height: props.height
}))
</script>

<style scoped>
.skeleton {
  width: v-bind('style.width || "100%"');
  height: v-bind('style.height || "1rem"');
}
</style>
