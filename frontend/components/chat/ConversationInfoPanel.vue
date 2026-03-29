<template>
  <div class="flex flex-col h-full bg-white overflow-hidden">
    <!-- Main body: scrollable top sections + pinned reasoning -->
    <div class="flex-1 flex flex-col min-h-0">
      <!-- Scrollable top 3 sections (task conversations only) -->
      <div v-if="isTaskConversation" class="flex-1 overflow-y-auto">
        <InfoPanelSummary />
        <InfoPanelDatasets />
        <InfoPanelDashboards />
      </div>

      <!-- Reasoning: pinned to bottom (or fills panel in non-task conversations) -->
      <InfoPanelReasoning :full-height="!isTaskConversation" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useChatStore } from '~/stores/chat'

const chatStore = useChatStore()
const isTaskConversation = computed(() => {
  const current = chatStore.currentConversation
  return !current || current.type === 'task'
})
</script>
