<template>
  <div class="bg-white dark:bg-neutral-800 rounded-lg shadow-md" :class="props.class">
    <slot />
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  class?: string
}>()
</script>
