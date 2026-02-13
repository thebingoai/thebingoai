<template>
  <div class="flex h-full">
    <!-- Settings Navigation -->
    <div class="w-56 border-r border-gray-200 p-4">
      <nav class="space-y-1">
        <button
          v-for="section in sections"
          :key="section.id"
          @click="currentSection = section.id"
          class="w-full rounded-lg px-3 py-2 text-left text-sm font-medium"
          :class="currentSection === section.id ? 'bg-gray-100 text-gray-900' : 'text-gray-700 hover:bg-gray-50'"
        >
          {{ section.name }}
        </button>
      </nav>
    </div>

    <!-- Settings Content -->
    <div class="flex-1 overflow-y-auto">
      <SettingsProfile v-if="currentSection === 'profile'" />
      <div v-else class="p-6">
        <h2 class="text-2xl font-bold text-gray-900 mb-4">{{ currentSectionName }}</h2>
        <p class="text-gray-500">This section is under construction.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const sections = [
  { id: 'connections', name: 'Connections' },
  { id: 'jobs', name: 'Jobs' },
  { id: 'memory', name: 'Memory' },
  { id: 'usage', name: 'Usage' },
  { id: 'profile', name: 'Profile' }
]

const currentSection = ref('profile')

const currentSectionName = computed(() => {
  return sections.find(s => s.id === currentSection.value)?.name || ''
})

definePageMeta({
  middleware: 'auth'
})
</script>
