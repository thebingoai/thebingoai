<template>
  <div class="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
    <h2 class="mb-4 font-semibold text-neutral-900 dark:text-neutral-100">
      Namespaces
    </h2>

    <div v-if="loading" class="space-y-2">
      <UiSkeleton v-for="i in 3" :key="i" height="32px" />
    </div>

    <div v-else-if="namespaces.length === 0">
      <p class="text-sm text-neutral-500 dark:text-neutral-400">
        No namespaces found
      </p>
    </div>

    <div v-else class="space-y-1">
      <NuxtLink
        v-for="namespace in namespaces"
        :key="namespace.name"
        :to="`/documents/${namespace.name}`"
        class="flex items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors"
        :class="{
          'bg-brand-100 text-brand-700 dark:bg-brand-900/20 dark:text-brand-400': selectedNamespace === namespace.name,
          'text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800': selectedNamespace !== namespace.name
        }"
      >
        <div class="flex items-center gap-2">
          <component :is="Folder" class="h-4 w-4" />
          <span>{{ namespace.name }}</span>
        </div>
        <UiBadge size="sm" variant="default">
          {{ namespace.vector_count }}
        </UiBadge>
      </NuxtLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Folder } from 'lucide-vue-next'
import type { NamespaceInfo } from '~/types'

interface Props {
  namespaces: NamespaceInfo[]
  selectedNamespace?: string
  loading?: boolean
}

withDefaults(defineProps<Props>(), {
  loading: false
})
</script>
