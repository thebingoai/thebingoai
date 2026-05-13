<template>
  <div class="min-h-screen flex">
    <!-- Left panel -->
    <AuthBrandingPanel :step="2" step-context="Connect Data" />

    <!-- Right panel -->
    <div class="flex-1 h-screen flex flex-col bg-white dark:bg-neutral-900 overflow-y-auto">
      <div class="flex-1 px-10 py-12 max-w-2xl mx-auto w-full">
        <!-- Header -->
        <h2 class="font-display text-4xl font-bold text-neutral-900 dark:text-neutral-50 mb-2">
          Plug in your <em class="italic text-purple-600">first source.</em>
        </h2>
        <p class="text-sm text-neutral-500 dark:text-neutral-400 mb-8 max-w-lg">
          Bingo reads your schema in read-only mode. Nothing gets written or copied — queries stay in your warehouse.
        </p>

        <!-- Loading skeleton -->
        <div v-if="loading" class="grid grid-cols-3 gap-3">
          <div v-for="i in 6" :key="i" class="h-[90px] rounded-xl bg-neutral-100 dark:bg-neutral-800 animate-pulse" />
        </div>

        <template v-else>
          <!-- Section: Default Connection -->
          <div v-if="sampleConnection" class="mb-8">
            <p class="text-[11px] tracking-widest font-medium text-neutral-400 dark:text-neutral-500 uppercase mb-3">
              Default Connection
            </p>
            <div class="grid grid-cols-3 gap-3">
              <button
                class="relative flex flex-col gap-1.5 p-3 rounded-xl border text-left transition-all focus:outline-none"
                :class="defaultConnectionEnabled
                  ? 'border-purple-500 bg-purple-50 dark:bg-purple-950/40 ring-1 ring-purple-500'
                  : 'border-neutral-200 dark:border-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600 hover:bg-neutral-50 dark:hover:bg-neutral-800/50'"
                @click="defaultConnectionEnabled = !defaultConnectionEnabled; selectedKey = ''"
              >
                <!-- Tick toggle -->
                <span class="absolute top-2 right-2">
                  <svg v-if="defaultConnectionEnabled" class="h-4 w-4 text-green-500" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                  </svg>
                  <svg v-else class="h-4 w-4 text-neutral-300 dark:text-neutral-600" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="10" cy="10" r="8"/>
                  </svg>
                </span>

                <!-- Icon -->
                <div class="h-10 w-10 shrink-0" v-if="connectorIcons[sampleConnection.db_type]" v-html="connectorIcons[sampleConnection.db_type]" />
                <div v-else class="h-7 w-7 rounded-md flex items-center justify-center text-[11px] font-bold bg-neutral-100 dark:bg-neutral-800 text-neutral-500">
                  {{ sampleConnection.db_type.charAt(0).toUpperCase() }}
                </div>

                <div class="min-w-0">
                  <p class="text-xs font-semibold text-neutral-800 dark:text-neutral-100 leading-tight truncate">{{ sampleConnection.name }}</p>
                  <p class="text-[11px] text-neutral-400 dark:text-neutral-500 mt-0.5">
                    {{ connectorTypeMap[sampleConnection.db_type]?.display_name || sampleConnection.db_type }}
                    <template v-if="sampleConnection.table_count != null"> · {{ sampleConnection.table_count }} tables</template>
                  </p>
                </div>
              </button>
            </div>
          </div>

          <!-- Section: Add a new source -->
          <div>
            <p class="text-[11px] tracking-widest font-medium text-neutral-400 dark:text-neutral-500 uppercase mb-3">
              Add a new source
            </p>
            <div class="grid grid-cols-3 gap-3">
              <button
                v-for="type in connectorTypes"
                :key="type.id"
                class="relative flex flex-col gap-1.5 p-3 rounded-xl border text-left transition-all focus:outline-none"
                :class="selectedKey === typeKey(type)
                  ? 'border-purple-500 bg-purple-50 dark:bg-purple-950/40 ring-1 ring-purple-500'
                  : 'border-neutral-200 dark:border-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600 hover:bg-neutral-50 dark:hover:bg-neutral-800/50'"
                @click="selectedKey = typeKey(type); defaultConnectionEnabled = false"
              >
                <!-- Recommended badge -->
                <span
                  v-if="type.id === 'postgres'"
                  class="absolute top-2 right-2 text-[9px] font-semibold tracking-widest uppercase text-purple-600 dark:text-purple-400 bg-purple-100 dark:bg-purple-950 px-1.5 py-0.5 rounded-full"
                >
                  Popular
                </span>

                <!-- Icon or letter badge -->
                <div class="h-10 w-10 shrink-0" v-if="connectorIcons[type.id]" v-html="connectorIcons[type.id]" />
                <div v-else class="h-7 w-7 rounded-md flex items-center justify-center text-[11px] font-bold shrink-0" :class="badgeClasses(type.badge_variant)">
                  {{ type.display_name.charAt(0).toUpperCase() }}
                </div>

                <div class="min-w-0">
                  <p class="text-xs font-semibold text-neutral-800 dark:text-neutral-100 leading-tight truncate">{{ type.display_name }}</p>
                  <p class="text-[11px] text-neutral-400 dark:text-neutral-500 mt-0.5">{{ type.description || type.card_meta_items?.[0] || '' }}</p>
                </div>
              </button>
            </div>
          </div>

          <!-- Network callout -->
          <div class="mt-6 flex items-center gap-3 text-sm text-neutral-500 dark:text-neutral-400">
            <div class="h-4 w-4 rounded-full border border-neutral-300 dark:border-neutral-600 flex items-center justify-center shrink-0">
              <span class="text-[9px]">?</span>
            </div>
            <span>
              <span class="font-medium text-neutral-600 dark:text-neutral-300">Network not open?</span>
              We can deploy a zero-trust tunnel. Takes ~2 minutes with a DevOps helper.
            </span>
            <button class="shrink-0 text-purple-600 dark:text-purple-400 font-medium hover:underline text-sm">Read guide</button>
          </div>
        </template>
      </div>

      <!-- Bottom action bar -->
      <div class="sticky bottom-0 border-t border-neutral-200 dark:border-neutral-800 px-10 py-4 flex items-center justify-end bg-white dark:bg-neutral-900">
        <button
          class="flex items-center gap-2 bg-purple-700 hover:bg-purple-800 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="!selectedKey && !defaultConnectionEnabled"
          @click="handleContinue"
        >
          <span>›</span>
          <span>Continue with {{ continueLabel }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import connectorPostgres from '~/assets/icons/connector/postgres.svg?raw'
import connectorMysqlWhite from '~/assets/icons/connector/mysql_white.svg?raw'
import connectorDataset from '~/assets/icons/connector/dataset.svg?raw'
import connectorFacebookAds from '~/assets/icons/connector/facebook_ads.svg?raw'
import connectorSqlite from '~/assets/icons/connector/sqlite.svg?raw'
import connectorBigquery from '~/assets/icons/connector/bigquery.svg?raw'
import connectorNotionWhite from '~/assets/icons/connector/notion_white.svg?raw'

interface ConnectorType {
  id: string
  display_name: string
  description: string
  default_port: number
  badge_variant: string
  version: string | null
  card_meta_items: string[]
}

interface DatabaseConnection {
  id: number
  name: string
  db_type: string
  table_count: number | null
  source_filename: string | null
  is_ephemeral: boolean
  profiling_status: string | null
}

const connectorIcons: Record<string, string> = {
  postgres:     connectorPostgres,
  mysql:        `<div class="h-10 w-10 shrink-0 rounded-xl bg-gradient-to-br from-cyan-600 to-blue-700 flex items-center justify-center shadow-sm ring-1 ring-cyan-400/30">${connectorMysqlWhite}</div>`,
  dataset:      connectorDataset,
  facebook_ads: connectorFacebookAds,
  sqlite:       connectorSqlite,
  bigquery:     connectorBigquery,
  notion:       `<div class="h-10 w-10 shrink-0 rounded-xl bg-gradient-to-br from-neutral-700 to-neutral-900 flex items-center justify-center shadow-sm ring-1 ring-neutral-400/20">${connectorNotionWhite}</div>`,
}

const api = useApi()
const loading = ref(true)
const connections = ref<DatabaseConnection[]>([])
const connectorTypes = ref<ConnectorType[]>([])
const selectedKey = ref<string>('')
const defaultConnectionEnabled = ref(false)

const connectorTypeMap = computed(() =>
  Object.fromEntries(connectorTypes.value.map(t => [t.id, t]))
)

const sampleConnection = computed(() =>
  connections.value.find(c => isSample(c)) ?? null
)

const isSample = (conn: DatabaseConnection) =>
  conn.source_filename?.includes('__bingo_sample__') ?? false

const sortedConnections = computed(() => {
  const nonEphemeral = connections.value.filter(c => !c.is_ephemeral)
  return [...nonEphemeral].sort((a, b) => {
    if (isSample(a) && !isSample(b)) return -1
    if (!isSample(a) && isSample(b)) return 1
    return 0
  })
})

const connKey = (conn: DatabaseConnection) => `conn:${conn.id}`
const typeKey = (type: ConnectorType) => `type:${type.id}`

const continueLabel = computed(() => {
  if (selectedKey.value) {
    const typeId = selectedKey.value.split(':')[1]
    return connectorTypeMap.value[typeId]?.display_name ?? typeId
  }
  if (defaultConnectionEnabled.value && sampleConnection.value) {
    return sampleConnection.value.name
  }
  return ''
})

function badgeClasses(variant: string) {
  const map: Record<string, string> = {
    info: 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400',
    warning: 'bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-400',
    secondary: 'bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400',
    success: 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400',
    danger: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400',
  }
  return map[variant] ?? map.secondary
}

function handleContinue() {
  if (selectedKey.value) {
    navigateTo('/settings')
  } else if (defaultConnectionEnabled.value) {
    navigateTo('/first-question')
  }
}

onMounted(async () => {
  try {
    const [conns, types] = await Promise.all([
      api.connections.list(),
      api.connections.getTypes(),
    ])
    connections.value = conns
    connectorTypes.value = types

    const sample = conns.find((c: DatabaseConnection) => isSample(c))
    if (sample) defaultConnectionEnabled.value = true
  } finally {
    loading.value = false
  }
})

definePageMeta({
  layout: false,
  middleware: 'auth',
  pageTransition: false,
  layoutTransition: false,
})
</script>
