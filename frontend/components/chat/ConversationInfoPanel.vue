<template>
  <div class="flex flex-col h-full bg-[var(--paper-1)]">
    <!-- Tab header strip -->
    <div class="flex items-center border-b border-[var(--line)] px-3.5 flex-shrink-0">
      <button
        class="py-3.5 px-2.5 text-[12px] font-semibold text-[var(--ink-0)] border-b-2 border-[var(--ember)] -mb-px cursor-default"
      >
        Datasets
      </button>
      <div class="flex-1" />
      <svg
        width="14" height="14" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"
        class="text-[var(--ink-2)]"
      >
        <polyline points="15 3 21 3 21 9" />
        <polyline points="9 21 3 21 3 15" />
        <line x1="21" y1="3" x2="14" y2="10" />
        <line x1="3" y1="21" x2="10" y2="14" />
      </svg>
    </div>

    <!-- Datasets content -->
    <div class="flex-1 overflow-y-auto p-[18px]" style="animation: bingo-tab-fade 0.22s ease-out;">
      <InfoPanelDatasets />
    </div>
  </div>
</template>

<script setup lang="ts">
</script>
