<template>
  <div class="p-6">
    <h2 class="text-2xl font-medium text-gray-900 dark:text-neutral-100 mb-1">Channels</h2>
    <p class="text-sm text-gray-500 dark:text-neutral-400 mb-6">Connect messaging platforms to your AI assistant.</p>

    <div v-if="entries.length === 0" class="text-sm text-gray-500 dark:text-neutral-400">
      No channels available.
    </div>
    <div v-else class="flex flex-wrap gap-4">
      <component
        v-for="entry in entries"
        :is="entry.component"
        :key="entry.id"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
const channels = useChannels()
const entries = computed(() => channels.list())
</script>
