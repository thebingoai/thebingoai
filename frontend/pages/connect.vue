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
  postgres: `<svg viewBox="0 0 432.071 445.383" xmlns="http://www.w3.org/2000/svg"><g fill="#336791"><path d="M323.205 324.227c2.833-23.601 1.984-27.062 19.563-23.239l4.463.392c13.517.615 31.199-2.174 41.587-7 22.362-10.376 35.622-27.7 13.572-23.148-50.297 10.376-53.755-6.655-53.755-6.655 53.111-78.803 75.313-178.836 56.149-203.322C352.514-5.534 262.036 26.049 260.522 26.869l-.482.089c-9.938-2.062-21.06-3.294-33.554-3.496-22.761-.374-40.032 5.967-53.133 15.904 0 0-161.408-66.498-153.899 83.628 1.597 31.936 45.777 241.655 98.47 178.31 19.259-23.163 37.871-42.748 37.871-42.748 9.242 6.14 20.307 9.272 31.912 8.147l.897-.765c-.281 2.876-.157 5.689.359 9.019-13.572 15.167-9.584 17.83-36.723 23.416-27.457 5.659-11.326 15.734-.797 18.367 12.768 3.193 42.305 7.716 62.268-20.224l-.795 3.188c5.325 4.26 4.965 30.619 5.72 49.452.756 18.834 1.05 36.196 3.86 45.739 2.808 9.54 8.315 33.577 36.2 26.732 23.413-5.736 35.94-20.08 37.448-44.38 1.183-19.093 3.585-25.045 3.507-48.974l2.525-1.812c.029 18.28 2.146 33.381 3.854 47.105 1.707 13.725 9.166 26.379 26.988 33.04 25.011 9.362 40.544-4.25 43.141-13.351 2.598-9.101 4.725-25.13 2.017-41.794-2.708-16.665-2.976-27.017-2.976-27.017s5.029-6.461 4.382-30.619c-.647-24.158-1.183-38.447 7.525-50.175l-.256.021z"/></g></svg>`,
  mysql: `<div class="h-10 w-10 shrink-0 rounded-xl bg-gradient-to-br from-cyan-600 to-blue-700 flex items-center justify-center shadow-sm ring-1 ring-cyan-400/30"><svg class="h-6 w-6" viewBox="0 0 256 252" xmlns="http://www.w3.org/2000/svg"><path fill="#ffffff" d="M235.648 194.212c-13.918-.347-24.705 1.045-33.752 4.872-2.61 1.043-6.786 1.044-7.134 4.35 1.392 1.392 1.566 3.654 2.784 5.567 2.09 3.479 5.741 8.177 9.047 10.614 3.653 2.783 7.308 5.566 11.134 8.002 6.786 4.176 14.442 6.611 21.053 10.787 3.829 2.434 7.654 5.568 11.482 8.177 1.914 1.39 3.131 3.654 5.568 4.523v-.521c-1.219-1.567-1.567-3.828-2.784-5.568-1.738-1.74-3.48-3.306-5.221-5.046-5.048-6.784-11.308-12.7-18.093-17.571-5.396-3.83-17.75-9.047-20.008-15.485 0 0-.175-.173-.348-.347 3.827-.348 8.35-1.566 12.005-2.436 5.912-1.565 11.308-1.217 17.398-2.784 2.783-.696 5.567-1.566 8.35-2.436v-1.565c-3.13-3.132-5.392-7.307-8.698-10.265-8.873-7.657-18.617-15.137-28.837-21.055-5.394-3.132-12.005-5.048-17.75-7.654-2.09-.696-5.567-1.566-6.784-3.306-3.133-3.827-4.698-8.699-7.135-13.047-5.04-9.568-9.866-20.184-14.576-30.23-3.13-6.786-5.044-13.572-8.872-19.834-17.92-29.577-37.406-47.497-67.33-65.07-6.438-3.653-14.093-5.219-22.27-7.132-4.348-.175-8.699-.522-13.046-.697-2.784-1.218-5.568-4.523-8.004-6.089C34.006 4.573 8.429-8.996 1.122 8.924c-4.698 11.308 6.96 22.441 10.96 28.143 2.96 4.001 6.786 8.524 8.874 13.046 1.392 3.132 1.566 6.263 2.958 9.569 2.784 7.654 5.221 16.178 8.872 23.311 1.914 3.653 4.001 7.48 6.437 10.786 1.392 2.088 3.827 2.957 4.348 5.915-2.435 3.48-2.61 8.7-4.003 13.049-6.263 19.66-3.826 44.017 5.046 58.457 2.784 4.348 9.395 13.572 18.268 10.091 7.83-3.132 6.09-13.046 8.35-21.75.522-2.09.176-3.48 1.219-4.872v.349c2.436 4.87 4.871 9.569 7.133 14.44 5.394 8.524 14.788 17.398 22.617 23.314 4.177 3.13 7.482 8.524 12.707 10.438v-.523h-.349c-1.044-1.566-2.61-2.261-4.001-3.48-3.131-3.13-6.612-6.958-9.047-10.438-7.306-9.744-13.745-20.357-19.486-31.665-2.784-5.392-5.22-11.308-7.481-16.701-1.045-2.088-1.045-5.22-2.784-6.263-2.61 3.827-6.437 7.133-8.351 11.83-3.304 7.481-3.653 16.702-4.871 26.27-.696.176-.349 0-.697.35-6.089-1.567-8.177-8.005-10.265-13.398-5.22-13.919-6.089-36.363-.175-52.19 1.565-4.176 8.702-17.398 5.915-21.23-1.391-3.654-6.263-5.742-8.872-8.525-2.959-3.477-6.088-7.829-8.004-11.83-4.697-10.264-6.96-21.75-11.833-32.015-2.262-4.871-6.263-9.744-9.57-14.093-3.653-4.872-7.829-8.351-10.788-14.268-1.043-2.088-2.436-5.046-1.218-7.133.173-1.74 1.044-2.611 2.784-3.131 2.784-1.218 10.613 1.044 13.398 2.09 7.482 2.434 13.572 4.871 19.834 8.699 2.958 1.913 6.088 5.568 9.742 6.612h4.35c6.787 1.566 14.267.522 20.707 2.09 11.485 2.958 21.75 7.654 31.665 12.7 30.23 15.66 54.762 37.929 71.68 66.506 2.436 4.175 3.48 8.003 5.566 12.354 4.175 8.7 9.396 17.574 13.572 26.097 4.348 8.872 8.699 17.75 14.093 25.402 2.959 4.001 14.787 6.09 20.008 8.177 3.827 1.567 9.918 3.132 13.572 5.046 6.787 3.48 13.398 7.481 19.834 11.308 3.305 1.914 13.572 6.09 14.268 10.265z"/></svg></div>`,
  dataset: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="3" width="18" height="18" rx="2" stroke="#6B7280" stroke-width="1.5"/><path d="M3 8h18" stroke="#6B7280" stroke-width="1.5"/><path d="M3 13h18" stroke="#6B7280" stroke-width="1.5"/><path d="M3 18h18" stroke="#6B7280" stroke-width="1.5"/><path d="M8 3v18" stroke="#6B7280" stroke-width="1.5"/><path d="M13 3v18" stroke="#6B7280" stroke-width="1.5"/></svg>`,
  facebook_ads: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M24 12c0-6.627-5.373-12-12-12S0 5.373 0 12c0 5.99 4.388 10.954 10.125 11.854V15.47H7.078V12h3.047V9.356c0-3.007 1.792-4.668 4.533-4.668 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.875V12h3.328l-.532 3.47h-2.796v8.385C19.612 22.954 24 17.99 24 12" fill="#1877F2"/></svg>`,
  sqlite: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C8.13 2 5 3.79 5 6v12c0 2.21 3.13 4 7 4s7-1.79 7-4V6c0-2.21-3.13-4-7-4z" stroke="#0F80CC" stroke-width="1.5" fill="none"/><path d="M5 6c0 2.21 3.13 4 7 4s7-1.79 7-4" stroke="#0F80CC" stroke-width="1.5"/><path d="M5 12c0 2.21 3.13 4 7 4s7-1.79 7-4" stroke="#0F80CC" stroke-width="1.5"/></svg>`,
  bigquery: `<svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg"><path d="M16 2C8.268 2 2 8.268 2 16s6.268 14 14 14 14-6.268 14-14S23.732 2 16 2zm6.5 20.5l-3-3a5.5 5.5 0 1 1 1.5-1.5l3 3-1.5 1.5zM16 20a4 4 0 1 1 0-8 4 4 0 0 1 0 8z" fill="#4285F4"/></svg>`,
  notion: `<div class="h-10 w-10 shrink-0 rounded-xl bg-gradient-to-br from-neutral-700 to-neutral-900 flex items-center justify-center shadow-sm ring-1 ring-neutral-400/20"><svg class="h-6 w-6" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="#ffffff" d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.968c-.42-.326-.981-.7-2.055-.607L3.01 2.295c-.466.046-.56.28-.374.466zm.793 3.08v13.904c0 .747.373 1.027 1.214.98l14.523-.84c.841-.046.935-.56.935-1.167V6.354c0-.606-.233-.933-.748-.887l-15.177.887c-.56.047-.747.327-.747.933zm14.337.745c.093.42 0 .84-.42.888l-.7.14v10.264c-.608.327-1.168.514-1.635.514-.748 0-.935-.234-1.495-.933l-4.577-7.186v6.952L12.21 19s0 .84-1.168.84l-3.222.186c-.093-.186 0-.653.327-.746l.84-.233V9.854L7.822 9.76c-.094-.42.14-1.026.793-1.073l3.456-.233 4.764 7.279v-6.44l-1.215-.139c-.093-.514.28-.887.747-.933zM1.936 1.035l13.31-.98c1.634-.14 2.055-.047 3.082.7l4.249 2.986c.7.513.934.653.934 1.213v16.378c0 1.026-.373 1.634-1.68 1.726l-15.458.934c-.98.047-1.448-.093-1.962-.747l-3.129-4.06c-.56-.747-.793-1.306-.793-1.96V2.667c0-.839.374-1.539 1.447-1.632z"/></svg></div>`,
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
