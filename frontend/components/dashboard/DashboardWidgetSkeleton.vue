<template>
  <div class="h-full w-full p-3 flex flex-col gap-2 animate-pulse">
    <!-- KPI skeleton -->
    <template v-if="type === 'kpi'">
      <div class="bg-gray-200 rounded h-3 w-1/3" />
      <div class="bg-gray-200 rounded h-8 w-1/2 mt-1" />
      <div class="bg-gray-200 rounded h-2.5 w-1/4 mt-auto" />
    </template>

    <!-- Chart skeleton -->
    <template v-else-if="type === 'chart'">
      <div class="bg-gray-200 rounded h-3 w-2/5" />
      <div class="flex-1 mt-1 relative overflow-hidden rounded bg-gray-100">
        <!-- Subtle grid lines -->
        <div class="absolute inset-x-0 top-1/4 h-px bg-gray-200" />
        <div class="absolute inset-x-0 top-1/2 h-px bg-gray-200" />
        <div class="absolute inset-x-0 top-3/4 h-px bg-gray-200" />
        <!-- Bar placeholders -->
        <div class="absolute bottom-0 inset-x-0 flex items-end gap-1.5 px-2 pb-0">
          <div class="flex-1 bg-gray-200 rounded-t" style="height: 55%" />
          <div class="flex-1 bg-gray-200 rounded-t" style="height: 75%" />
          <div class="flex-1 bg-gray-200 rounded-t" style="height: 40%" />
          <div class="flex-1 bg-gray-200 rounded-t" style="height: 90%" />
          <div class="flex-1 bg-gray-200 rounded-t" style="height: 60%" />
          <div class="flex-1 bg-gray-200 rounded-t" style="height: 45%" />
        </div>
      </div>
    </template>

    <!-- Table skeleton -->
    <template v-else-if="type === 'table'">
      <!-- Header row -->
      <div class="flex gap-2 pb-1 border-b border-gray-200">
        <div class="bg-gray-300 rounded h-3 w-1/4" />
        <div class="bg-gray-300 rounded h-3 w-1/5" />
        <div class="bg-gray-300 rounded h-3 w-1/4" />
        <div class="bg-gray-300 rounded h-3 w-1/6" />
      </div>
      <!-- Data rows -->
      <div v-for="i in 5" :key="i" class="flex gap-2 py-1">
        <div class="bg-gray-200 rounded h-2.5" :class="i % 2 === 0 ? 'w-1/4' : 'w-1/3'" />
        <div class="bg-gray-200 rounded h-2.5" :class="i % 3 === 0 ? 'w-1/6' : 'w-1/5'" />
        <div class="bg-gray-200 rounded h-2.5" :class="i % 2 === 0 ? 'w-1/5' : 'w-1/4'" />
        <div class="bg-gray-200 rounded h-2.5" :class="i % 3 === 0 ? 'w-1/5' : 'w-1/6'" />
      </div>
    </template>

    <!-- Text skeleton -->
    <template v-else-if="type === 'text'">
      <div class="bg-gray-200 rounded h-3 w-3/4" />
      <div class="bg-gray-200 rounded h-3 w-full" />
      <div class="bg-gray-200 rounded h-3 w-5/6" />
      <div class="bg-gray-200 rounded h-3 w-2/3" />
    </template>

    <!-- Filter skeleton -->
    <template v-else-if="type === 'filter'">
      <div class="bg-gray-200 rounded h-2.5 w-1/4 mb-1" />
      <div class="flex flex-wrap gap-1.5">
        <div class="bg-gray-200 rounded-full h-6 w-16" />
        <div class="bg-gray-200 rounded-full h-6 w-20" />
        <div class="bg-gray-200 rounded-full h-6 w-14" />
        <div class="bg-gray-200 rounded-full h-6 w-18" />
      </div>
    </template>

    <!-- Fallback -->
    <template v-else>
      <div class="bg-gray-200 rounded h-3 w-1/2" />
      <div class="flex-1 bg-gray-100 rounded mt-1" />
    </template>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  type: string
}>()
</script>
