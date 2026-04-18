<template>
  <div class="flex flex-col items-center justify-center py-12 text-center">
    <div v-if="icon || $slots.icon" class="mb-4 rounded-full bg-gray-100 dark:bg-neutral-700 p-4">
      <component v-if="icon" :is="icon" class="h-8 w-8 text-gray-400 dark:text-neutral-400" />
      <slot v-else name="icon" />
    </div>

    <h3 class="mb-2 text-lg font-normal text-gray-900 dark:text-white">
      {{ title }}
    </h3>

    <p class="mb-6 max-w-sm text-sm text-gray-600 dark:text-gray-300">
      {{ description }}
    </p>

    <slot name="action" />
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'

interface Props {
  title: string
  description?: string
  icon?: Component
}

defineProps<Props>()
</script>
