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

      <!-- Slack -->
      <ChannelWaitlistCard
        name="Slack"
        description="Invite @bingo to any channel. DM for private tasks or reply to scheduled digests."
        mailto-address="hello@thebingo.ai"
        mailto-subject="Slack channel integration - waitlist"
        status="available"
        icon-bg="bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400"
      >
        <template #icon>
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"/>
          </svg>
        </template>
      </ChannelWaitlistCard>

      <!-- Email -->
      <ChannelWaitlistCard
        name="Email"
        description="Reply to scheduled digests to kick off new tasks directly from your inbox."
        mailto-address="hello@thebingo.ai"
        mailto-subject="Email channel integration - waitlist"
        status="available"
        icon-bg="bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
      >
        <template #icon>
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect width="20" height="16" x="2" y="4" rx="2"/>
            <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
          </svg>
        </template>
      </ChannelWaitlistCard>

      <!-- Discord -->
      <ChannelWaitlistCard
        name="Discord"
        description="Coming soon — add to our waitlist and we'll notify you when it's ready."
        mailto-address="hello@thebingo.ai"
        mailto-subject="Discord channel integration - waitlist"
        status="waitlist"
        icon-bg="bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400"
      >
        <template #icon>
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z"/>
          </svg>
        </template>
      </ChannelWaitlistCard>
    </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const channels = useChannels()
const registeredEntries = computed(() => channels.list())
</script>
