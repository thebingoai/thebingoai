<template>
  <header
    class="fixed right-0 top-0 z-30 h-header border-b border-neutral-200 bg-white transition-all dark:border-neutral-800 dark:bg-neutral-900"
    :class="{
      'left-0 lg:left-sidebar': !settings.sidebarCollapsed,
      'left-0 lg:left-sidebar-collapsed': settings.sidebarCollapsed
    }"
  >
    <div class="flex h-full items-center justify-between px-4">
      <!-- Mobile menu button -->
      <button
        @click="showMobileMenu = true"
        class="rounded-lg p-2 text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800 lg:hidden"
        aria-label="Open menu"
      >
        <component :is="Menu" class="h-6 w-6" />
      </button>

      <!-- Page title (optional - could show current page name) -->
      <div class="hidden text-lg font-semibold text-neutral-900 dark:text-neutral-100 lg:block">
        {{ pageTitle }}
      </div>

      <!-- Right side actions -->
      <div class="flex items-center gap-2">
        <!-- Connection status -->
        <div class="hidden items-center gap-2 rounded-full bg-neutral-100 px-3 py-1.5 text-sm dark:bg-neutral-800 lg:flex">
          <div
            class="h-2 w-2 rounded-full"
            :class="{
              'bg-success-500': settings.connectionStatus === 'connected',
              'bg-warning-500': settings.connectionStatus === 'checking',
              'bg-error-500': settings.connectionStatus === 'disconnected'
            }"
          />
          <span class="text-neutral-700 dark:text-neutral-300">
            {{ statusText }}
          </span>
        </div>

        <!-- Theme toggle -->
        <button
          @click="toggleTheme"
          class="rounded-lg p-2 text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
          aria-label="Toggle theme"
        >
          <component :is="colorMode.preference === 'dark' ? Sun : Moon" class="h-5 w-5" />
        </button>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { Menu, Moon, Sun } from 'lucide-vue-next'

const settings = useSettingsStore()
const colorMode = useColorMode()
const route = useRoute()
const showMobileMenu = inject('showMobileMenu', ref(false))

const pageTitle = computed(() => {
  const path = route.path
  if (path === '/') return 'Dashboard'
  if (path.startsWith('/documents')) return 'Documents'
  if (path.startsWith('/search')) return 'Search'
  if (path.startsWith('/chat')) return 'Chat'
  if (path.startsWith('/jobs')) return 'Jobs'
  if (path.startsWith('/settings')) return 'Settings'
  return 'LLM-MD-CLI'
})

const statusText = computed(() => {
  switch (settings.connectionStatus) {
    case 'connected': return 'Connected'
    case 'checking': return 'Checking...'
    case 'disconnected': return 'Disconnected'
    default: return 'Unknown'
  }
})

const toggleTheme = () => {
  colorMode.preference = colorMode.preference === 'dark' ? 'light' : 'dark'
}
</script>
