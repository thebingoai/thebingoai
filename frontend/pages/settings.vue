<template>
  <div class="flex h-full pt-2 relative" :class="isMobile ? 'flex-col' : ''">
    <!-- Close Button (mobile: fixed, aligned with hamburger; desktop: absolute top-right) -->
    <button
      v-if="isMobile"
      @click="router.push('/chat')"
      class="fixed right-3 top-1.5 z-30 rounded-lg p-2 pt-4 mr-1 transition-colors hover:bg-gray-100"
      aria-label="Close settings"
    >
      <X class="h-5 w-5 text-gray-500" />
    </button>
    <button
      v-else
      @click="router.push('/chat')"
      class="absolute top-0 right-6 p-2 rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-900 transition-colors"
      aria-label="Close settings"
    >
      <X class="h-5 w-5" />
    </button>

    <!-- Settings Navigation -->
    <div
      :class="isMobile
        ? 'flex items-center gap-2 overflow-x-auto px-4 pb-3 border-b border-gray-200 dark:border-neutral-700 shrink-0'
        : 'w-56 border-r border-gray-200 dark:border-neutral-700 p-4 flex flex-col justify-between'"
    >
      <nav :class="isMobile ? 'flex gap-1' : 'space-y-1'">
        <button
          v-for="section in sections"
          :key="section.id"
          @click="currentSection = section.id"
          :class="[
            isMobile
              ? 'whitespace-nowrap px-3 py-1.5 text-xs rounded-full'
              : 'w-full rounded-lg px-3 py-2 text-left text-sm font-light',
            currentSection === section.id ? 'bg-gray-100 dark:bg-neutral-700 text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-neutral-800'
          ]"
        >
          {{ section.name }}
        </button>
      </nav>

      <div v-if="!isMobile" class="pt-4 border-t border-gray-200 dark:border-neutral-700 text-xs text-gray-400 dark:text-gray-300 space-y-1">
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
      <SettingsApiKeys v-else-if="currentSection === 'credits' && featureConfig?.credits_enabled === false" />
      <SettingsCredits v-else-if="currentSection === 'credits' && featureConfig?.credits_enabled === true" />
      <SettingsChannels v-else-if="currentSection === 'channels'" />
      <component
        v-else-if="activePluginTab"
        :is="activePluginTab.component"
      />
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
const { isMobile } = useIsMobile()
const { config: featureConfig } = useFeatureConfig()
const settingsTabs = useSettingsTabs()

const { data: appInfo } = useLazyFetch('/api/info')

const pluginTabs = computed(() =>
  settingsTabs.list().filter(tab => !tab.condition || tab.condition())
)

const sections = computed(() => {
  const base = [
    { id: 'connections', name: 'Connections' },
    { id: 'skills', name: 'Skills' },
    { id: 'jobs', name: 'Jobs' },
    { id: 'memory', name: 'Memory' },
    { id: 'credits', name: featureConfig.value?.credits_enabled === false ? 'API Keys' : 'Credits & API Keys' },
    { id: 'profile', name: 'Profile' },
  ]
  if (featureConfig.value?.telegram_enabled) {
    base.push({ id: 'channels', name: 'Channels' })
  }
  for (const tab of pluginTabs.value) {
    if (!base.find(s => s.id === tab.id)) {
      base.push({ id: tab.id, name: tab.label })
    }
  }
  return base
})

const route = useRoute()
const initialTab = (route.query.tab as string) || 'connections'
const currentSection = ref(
  sections.value.some(s => s.id === initialTab) ? initialTab : 'connections'
)

const currentSectionName = computed(() => {
  return sections.value.find(s => s.id === currentSection.value)?.name || ''
})

const activePluginTab = computed(() =>
  pluginTabs.value.find(tab => tab.id === currentSection.value),
)

definePageMeta({
  middleware: 'auth'
})
</script>
