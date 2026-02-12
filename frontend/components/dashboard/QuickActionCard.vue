<template>
  <NuxtLink
    :to="to"
    class="group block rounded-lg border border-neutral-200 bg-white p-6 shadow-sm transition-all hover:shadow-md hover:border-brand-300 dark:border-neutral-800 dark:bg-neutral-900 dark:hover:border-brand-700"
  >
    <div class="flex items-start gap-4">
      <div class="rounded-lg bg-brand-100 p-3 transition-colors group-hover:bg-brand-200 dark:bg-brand-900/20 dark:group-hover:bg-brand-900/30">
        <component :is="icon" class="h-6 w-6 text-brand-600 dark:text-brand-400" />
      </div>
      <div class="flex-1">
        <h3 class="font-semibold text-neutral-900 dark:text-neutral-100">
          {{ title }}
        </h3>
        <p class="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          {{ description }}
        </p>
      </div>
      <component :is="ArrowRight" class="h-5 w-5 text-neutral-400 transition-transform group-hover:translate-x-1" />
    </div>
  </NuxtLink>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { ArrowRight } from 'lucide-vue-next'

interface Props {
  title: string
  description: string
  icon: Component
  to: string
}

defineProps<Props>()
</script>
