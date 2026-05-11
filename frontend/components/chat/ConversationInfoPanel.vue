<template>
  <div class="flex flex-col h-full bg-[var(--paper-1)]">
    <!-- Tab header strip -->
    <div class="flex items-center border-b border-[var(--line)] px-3.5 flex-shrink-0">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="py-3.5 px-2.5 text-[12px] font-semibold -mb-px cursor-default transition-colors"
        :class="activeTab === tab.key
          ? 'text-[var(--ink-0)] border-b-2 border-[var(--ember)]'
          : 'text-[var(--ink-2)] border-b-2 border-transparent hover:text-[var(--ink-1)]'"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
      <div class="flex-1" />
    </div>

    <!-- Tab content -->
    <div class="flex-1 overflow-y-auto p-[18px]" style="animation: bingo-tab-fade 0.22s ease-out;">
      <InfoPanelDatasets v-if="activeTab === 'datasets'" />
      <InfoPanelBriefings v-else-if="activeTab === 'briefings'" />
    </div>
  </div>
</template>

<script setup lang="ts">
const chatStore = useChatStore()

const isAssistant = computed(() =>
  chatStore.currentThreadId === chatStore.permanentConversation?.id
)

const tabs = computed(() => {
  const items = [{ key: 'datasets', label: 'Datasets' }]
  if (isAssistant.value) {
    items.push({ key: 'briefings', label: 'Briefings' })
  }
  return items
})
const activeTab = ref('datasets')

// Reset to datasets tab when leaving the assistant thread
watch(isAssistant, (val) => {
  if (!val && activeTab.value === 'briefings') {
    activeTab.value = 'datasets'
  }
})
</script>
