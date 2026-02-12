<template>
  <aside
    class="fixed left-0 top-0 z-40 h-screen border-r border-neutral-200 bg-white transition-all dark:border-neutral-800 dark:bg-neutral-900"
    :class="{
      'w-sidebar': !settings.sidebarCollapsed,
      'w-sidebar-collapsed': settings.sidebarCollapsed
    }"
  >
    <!-- Logo -->
    <div class="flex h-header items-center border-b border-neutral-200 px-4 dark:border-neutral-800">
      <component
        :is="FileText"
        class="h-6 w-6 text-brand-600 dark:text-brand-400"
      />
      <Transition name="fade">
        <span
          v-if="!settings.sidebarCollapsed"
          class="ml-3 text-lg font-semibold text-neutral-900 dark:text-neutral-100"
        >
          LLM-MD-CLI
        </span>
      </Transition>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 overflow-y-auto px-3 py-4">
      <ul class="space-y-1">
        <li v-for="item in NAV_ITEMS" :key="item.href">
          <NuxtLink
            :to="item.href"
            class="flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors"
            :class="{
              'bg-brand-100 text-brand-700 dark:bg-brand-900/20 dark:text-brand-400': isActive(item.href),
              'text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800': !isActive(item.href),
              'justify-center': settings.sidebarCollapsed
            }"
          >
            <component :is="item.icon" class="h-5 w-5 flex-shrink-0" />
            <Transition name="fade">
              <span v-if="!settings.sidebarCollapsed" class="ml-3">
                {{ item.name }}
              </span>
            </Transition>
          </NuxtLink>
        </li>
      </ul>
    </nav>

    <!-- Collapse toggle -->
    <div class="border-t border-neutral-200 p-3 dark:border-neutral-800">
      <button
        @click="settings.toggleSidebar()"
        class="flex w-full items-center rounded-lg px-3 py-2 text-sm font-medium text-neutral-700 transition-colors hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
        :class="{ 'justify-center': settings.sidebarCollapsed }"
      >
        <component
          :is="settings.sidebarCollapsed ? ChevronRight : ChevronLeft"
          class="h-5 w-5 flex-shrink-0"
        />
        <Transition name="fade">
          <span v-if="!settings.sidebarCollapsed" class="ml-3">
            Collapse
          </span>
        </Transition>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { FileText, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { NAV_ITEMS } from '~/utils/constants'

const settings = useSettingsStore()
const route = useRoute()

const isActive = (path: string) => {
  if (path === '/') {
    return route.path === '/'
  }
  return route.path.startsWith(path)
}
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
