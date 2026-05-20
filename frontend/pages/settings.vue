<template>
  <div class="flex h-full relative" :class="isMobile ? 'flex-col' : ''">
    <button
      v-if="!isMobile"
      @click="router.push('/chat')"
      class="absolute top-10 right-6 p-1.5 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:text-neutral-500 dark:hover:bg-neutral-800 dark:hover:text-neutral-300 transition-colors z-10"
      aria-label="Close settings"
    >
      <X class="h-4 w-4" />
    </button>

    <!-- Mobile close button -->
    <button
      v-else
      @click="router.push('/chat')"
      class="fixed right-3 top-1.5 z-30 rounded-lg p-1.5 pt-4 mr-1 text-gray-400 dark:text-neutral-500 dark:hover:bg-neutral-800 dark:hover:text-neutral-300 transition-colors hover:bg-gray-100 hover:text-gray-700"
      aria-label="Close settings"
    >
      <X class="h-4 w-4" />
    </button>

    <!-- Settings Navigation Panel -->
    <div
      :class="isMobile
        ? 'flex items-center gap-2 overflow-x-auto px-4 pb-3 border-b border-gray-200 dark:border-neutral-700 shrink-0'
        : 'w-56 border-r border-gray-200 dark:border-neutral-700 flex flex-col justify-between flex-shrink-0 overflow-hidden'"
    >
      <nav :class="isMobile ? 'flex gap-1' : 'flex-1 min-h-0 overflow-y-auto space-y-1'">
        <template v-for="(section, index) in sections" :key="section.id">
          <div
            v-if="!isMobile && section.group && (index === 0 || sections[index - 1].group !== section.group)"
            :class="[
              'flex items-center gap-2 px-3 pt-4 pb-2 eyebrow font-semibold text-gray-700 dark:text-gray-200',
              index === 0 ? 'mt-0' : 'mt-3 border-t border-gray-200 dark:border-neutral-700',
            ]"
          >
            <span class="h-1 w-1 rounded-full bg-gray-400 dark:bg-neutral-500" />
            {{ section.group }}
          </div>
          <button
            @click="selectSection(section.id)"
            :class="[
              isMobile
                ? 'whitespace-nowrap px-3 py-1.5 text-xs rounded-full'
                : 'w-full rounded-lg px-3 py-2 text-left text-sm font-light',
              currentSection === section.id ? 'bg-gray-100 dark:bg-neutral-700 text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-neutral-800'
            ]"
          >
            {{ section.name }}
          </button>
        </template>
      </nav>

      <div v-if="!isMobile" class="px-4 py-3 border-t border-gray-200 dark:border-neutral-700 flex-shrink-0">
        <p class="text-[11px] text-gray-400 dark:text-neutral-500">
          {{ appInfo?.edition || 'Community' }} Edition · v{{ appInfo?.version || '1.0.0' }}
        </p>
      </div>
    </div>

    <!-- Settings Content -->
    <div class="flex-1 overflow-y-auto">
      <SettingsAgent       v-if="currentSection === 'agent'" />
      <SettingsConnections v-else-if="currentSection === 'connections'" />
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
        <h2 class="settings-h1 text-3xl text-gray-900 mb-4">{{ currentSectionName }}</h2>
        <p class="text-gray-500">This section is under construction.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { X, Database, Sparkles, Clock, Brain, Key, User, MessageSquare, Shield, Settings } from 'lucide-vue-next'

const router = useRouter()
const { isMobile } = useIsMobile()
const { config: featureConfig } = useFeatureConfig()
const settingsTabs = useSettingsTabs()
const { currentSection } = useSettingsState()
const { data: appInfo } = useLazyFetch<{ edition?: string; version?: string }>('/api/info')
const api = useApi() as any
const channels = useChannels()

const counts = ref<Record<string, number | undefined>>({})

async function loadCounts() {
  const results = await Promise.allSettled([
    (api.connections.list() as Promise<any[]>).then((r: any[]) => ({ key: 'connections', val: r.length })),
    (api.skills.list() as Promise<any[]>).then((r: any[]) => ({ key: 'skills', val: r.length })),
    (api.heartbeatJobs.list() as Promise<any[]>).then((r: any[]) => ({ key: 'jobs', val: r.length })),
    (api.memory.listEntries() as Promise<{ entries: any[] }>).then((r: { entries: any[] }) => ({ key: 'memory', val: r.entries.length })),
  ])
  for (const result of results) {
    if (result.status === 'fulfilled') {
      counts.value[result.value.key] = result.value.val
    }
  }
}

onMounted(loadCounts)

const SECTION_ICONS: Record<string, any> = {
  connections: Database,
  skills: Sparkles,
  jobs: Clock,
  memory: Brain,
  credits: Key,
  profile: User,
  channels: MessageSquare,
  admin: Shield,
}

const pluginTabs = computed(() =>
  settingsTabs.list().filter((tab: any) => !tab.condition || tab.condition())
)

interface Section {
  id: string
  name: string
  group?: string
  order: number
}

const GROUP_ORDER: Record<string, number> = {
  Workspace: 1,
  'Data Platform': 2,
  Account: 3,
  Administration: 4,
}

const sections = computed<Section[]>(() => {
  const base: Section[] = [
    { id: 'agent', name: 'Agent', group: 'Workspace', order: 5 },
    { id: 'connections', name: 'Connections', group: 'Workspace', order: 10 },
    { id: 'channels', name: 'Channels', group: 'Workspace', order: 20 },
    { id: 'skills', name: 'Skills', group: 'Workspace', order: 30 },
    { id: 'memory', name: 'Memory', group: 'Workspace', order: 40 },
    { id: 'jobs', name: 'Jobs', group: 'Workspace', order: 50 },
    { id: 'profile', name: 'Profile', group: 'Account', order: 10 },
    {
      id: 'credits',
      name: featureConfig.value?.credits_enabled === false ? 'API Keys' : 'Credits & API Keys',
      group: 'Account',
      order: 20,
    },
  ]
  const channelsHidden = !featureConfig.value?.telegram_enabled
  const all: Section[] = base.filter(s => !(s.id === 'channels' && channelsHidden))
  for (const tab of pluginTabs.value) {
    if (all.find(s => s.id === tab.id)) continue
    all.push({
      id: tab.id,
      name: tab.label,
      group: tab.group,
      order: tab.order ?? 100,
    })
  }
  return all.sort((a, b) => {
    const ga = GROUP_ORDER[a.group ?? ''] ?? 99
    const gb = GROUP_ORDER[b.group ?? ''] ?? 99
    return ga !== gb ? ga - gb : a.order - b.order
  })
})

// Sync initial section from URL query param
const route = useRoute()

// Legacy deep links: users/members/invitations were merged into the People page.
const LEGACY_TAB_REDIRECTS: Record<string, string> = {
  users: 'people',
  members: 'people',
  invitations: 'people',
}

watch([() => route.query.tab, sections], ([tab, secs]) => {
  const raw = (tab as string) || 'agent'
  const id = LEGACY_TAB_REDIRECTS[raw] ?? raw
  if (secs.some(s => s.id === id)) {
    currentSection.value = id
  }
}, { immediate: true })

function selectSection(id: string) {
  currentSection.value = id
  const next = { ...route.query }
  if (id === 'agent') delete next.tab
  else next.tab = id
  router.replace({ query: next })
}

const currentSectionName = computed(() => {
  return sections.value.find(s => s.id === currentSection.value)?.name || ''
})

const activePluginTab = computed(() =>
  pluginTabs.value.find((tab: any) => tab.id === currentSection.value),
)

definePageMeta({
  middleware: 'auth'
})
</script>
