<template>
  <div class="flex flex-col h-full overflow-hidden">

    <!-- Page header -->
    <div class="px-7 pt-3 pb-2 border-b border-[var(--line)] flex-shrink-0">
      <p class="eyebrow mb-0.5 text-gray-400 dark:text-neutral-500">Settings · Channels</p>
      <h1 class="settings-h1 text-3xl text-gray-900 dark:text-neutral-100 mb-1">Channels</h1>
    </div>

    <!-- Scrolling body -->
    <div class="flex-1 overflow-y-auto px-7 py-6 space-y-6">
      <p class="text-sm text-gray-500 dark:text-neutral-400 max-w-2xl">Bring Bingo into your team's messaging. Each channel becomes a route for scheduled digests and a two-way chat surface.</p>

    <div class="flex flex-wrap gap-4">
      <!-- Plugin-registered channels (e.g. Telegram) -->
      <component
        v-for="entry in registeredEntries"
        :is="entry.component"
        :key="entry.id"
      />
    </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const channels = useChannels()
const registeredEntries = computed(() => channels.list())
</script>
