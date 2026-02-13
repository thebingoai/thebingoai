<template>
  <div class="bg-white rounded-lg shadow-md" :class="props.class">
    <slot />
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  class?: string
}>()
</script>
