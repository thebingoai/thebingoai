<template>
  <div class="flex flex-col h-full bg-white overflow-hidden">
    <!-- Main body: scrollable top sections + pinned reasoning -->
    <div class="flex-1 flex flex-col min-h-0">
      <!-- Scrollable top 3 sections -->
      <div class="flex-1 overflow-y-auto">
        <InfoPanelSummary />
        <InfoPanelDatasets />
        <InfoPanelDashboards />
      </div>

      <!-- Reasoning: pinned to bottom -->
      <InfoPanelReasoning />
    </div>
  </div>
</template>
