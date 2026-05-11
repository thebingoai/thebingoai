<template>
  <div class="flex flex-col h-full bg-white dark:bg-neutral-900 overflow-hidden">
    <!-- Main body: scrollable top sections + pinned reasoning -->
    <div class="flex-1 flex flex-col min-h-0">
      <!-- Scrollable sections (task conversations) -->
      <div v-if="isTaskConversation" class="flex-1 overflow-y-auto">
        <InfoPanelSummary />
        <InfoPanelDatasets />
        <InfoPanelDashboards />
      </div>

      <!-- Scrollable sections (BingoAI chat) -->
      <div v-if="!isTaskConversation && hasSkillSuggestions" class="flex-shrink-0 overflow-y-auto max-h-[40%]">
        <InfoPanelSkills />
      </div>

      <!-- Reasoning: pinned to bottom (or fills panel when no other sections) -->
      <InfoPanelReasoning :full-height="!isTaskConversation && !hasSkillSuggestions" />
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
const hasSkillSuggestions = computed(() => chatStore.pendingSkillSuggestions.length > 0)
</script>
