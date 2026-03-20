<template>
  <div class="flex h-full pt-20 relative">
    <!-- Close Button -->
    <button
      @click="router.push('/chat')"
      class="absolute top-6 right-6 p-2 rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-900 transition-colors"
      aria-label="Close settings"
    >
      <X class="h-5 w-5" />
    </button>

    <!-- Settings Navigation -->
    <div class="w-56 border-r border-gray-200 p-4 flex flex-col justify-between">
      <nav class="space-y-1">
        <button
          v-for="section in sections"
          :key="section.id"
          @click="currentSection = section.id"
          class="w-full rounded-lg px-3 py-2 text-left text-sm font-light"
          :class="currentSection === section.id ? 'bg-gray-100 text-gray-900' : 'text-gray-700 hover:bg-gray-50'"
        >
          {{ section.name }}
        </button>
      </nav>

      <div class="pt-4 border-t border-gray-200 text-xs text-gray-400 space-y-1">
        <p>{{ appInfo?.edition || 'Community' }} Edition</p>
        <p>v{{ appInfo?.version || '1.0.0' }}</p>
      </div>
    </div>

    <!-- Settings Content -->
    <div class="flex-1 overflow-y-auto">
      <SettingsConnections v-if="currentSection === 'connections'" />
      <SettingsSkills v-else-if="currentSection === 'skills'" />
      <SettingsJobs v-else-if="currentSection === 'jobs'" />
      <SettingsMemory v-else-if="currentSection === 'memory'" />
      <SettingsProfile v-else-if="currentSection === 'profile'" />
      <div v-else class="p-6">
        <h2 class="text-2xl font-medium text-gray-900 mb-4">{{ currentSectionName }}</h2>
        <p class="text-gray-500">This section is under construction.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { X } from 'lucide-vue-next'

const router = useRouter()

const { data: appInfo } = await useFetch('/api/info')

const sections = [
  { id: 'connections', name: 'Connections' },
  { id: 'skills', name: 'Skills' },
  { id: 'jobs', name: 'Jobs' },
  { id: 'memory', name: 'Memory' },
  { id: 'usage', name: 'Usage' },
  { id: 'profile', name: 'Profile' }
]

const currentSection = ref('connections')

const currentSectionName = computed(() => {
  return sections.find(s => s.id === currentSection.value)?.name || ''
})

definePageMeta({
  middleware: 'auth'
})
</script>
