<template>
  <!-- Overlay -->
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="isOpen"
        class="fixed inset-0 z-50 bg-black/50 lg:hidden"
        @click="close"
      />
    </Transition>

    <!-- Drawer -->
    <Transition name="slide">
      <div
        v-if="isOpen"
        class="fixed left-0 top-0 z-50 h-screen w-sidebar bg-white shadow-xl dark:bg-neutral-900 lg:hidden"
      >
        <!-- Header with close button -->
        <div class="flex h-header items-center justify-between border-b border-neutral-200 px-4 dark:border-neutral-800">
          <div class="flex items-center">
            <component :is="FileText" class="h-6 w-6 text-brand-600 dark:text-brand-400" />
            <span class="ml-3 text-lg font-semibold text-neutral-900 dark:text-neutral-100">
              LLM-MD-CLI
            </span>
          </div>
          <button
            @click="close"
            class="rounded-lg p-2 text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
            aria-label="Close menu"
          >
            <component :is="X" class="h-5 w-5" />
          </button>
        </div>

        <!-- Navigation -->
        <nav class="overflow-y-auto px-3 py-4">
          <ul class="space-y-1">
            <li v-for="item in NAV_ITEMS" :key="item.href">
              <NuxtLink
                :to="item.href"
                @click="close"
                class="flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors"
                :class="{
                  'bg-brand-100 text-brand-700 dark:bg-brand-900/20 dark:text-brand-400': isActive(item.href),
                  'text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800': !isActive(item.href)
                }"
              >
                <component :is="item.icon" class="h-5 w-5 flex-shrink-0" />
                <span class="ml-3">{{ item.name }}</span>
              </NuxtLink>
            </li>
          </ul>
        </nav>

        <!-- Footer with theme toggle -->
        <div class="absolute bottom-0 left-0 right-0 border-t border-neutral-200 p-3 dark:border-neutral-800">
          <button
            @click="toggleTheme"
            class="flex w-full items-center rounded-lg px-3 py-2 text-sm font-medium text-neutral-700 transition-colors hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
          >
            <component :is="colorMode.preference === 'dark' ? Sun : Moon" class="h-5 w-5 flex-shrink-0" />
            <span class="ml-3">
              {{ colorMode.preference === 'dark' ? 'Light Mode' : 'Dark Mode' }}
            </span>
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { FileText, X, Moon, Sun } from 'lucide-vue-next'
import { NAV_ITEMS } from '~/utils/constants'

const isOpen = ref(false)
const colorMode = useColorMode()
const route = useRoute()

// Provide to AppHeader
provide('showMobileMenu', isOpen)

const close = () => {
  isOpen.value = false
}

const isActive = (path: string) => {
  if (path === '/') {
    return route.path === '/'
  }
  return route.path.startsWith(path)
}

const toggleTheme = () => {
  colorMode.preference = colorMode.preference === 'dark' ? 'light' : 'dark'
}

// Close on route change
watch(() => route.path, close)
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

.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(-100%);
}
</style>
