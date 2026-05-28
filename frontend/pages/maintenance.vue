<template>
  <div class="min-h-screen flex flex-col items-center justify-center bg-white dark:bg-neutral-900 px-6 py-12 text-center">
    <!-- Dark mode toggle (top right) -->
    <button
      class="absolute top-4 right-4 p-2 rounded-lg text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
      :aria-label="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
      @click="isDark = !isDark"
    >
      <Sun v-if="isDark" class="h-4 w-4" />
      <Moon v-else class="h-4 w-4" />
    </button>

    <img
      :src="isDark ? '/logo/logo-white.png' : '/logo/logo-black.png'"
      alt="Bingo"
      class="h-12 w-auto mb-10"
    />

    <h1 class="font-display text-5xl font-bold text-neutral-900 dark:text-neutral-50 mb-4">
      We'll be back shortly.
    </h1>

    <p class="max-w-md text-base text-neutral-600 dark:text-neutral-400">
      {{ message }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { Sun, Moon } from 'lucide-vue-next'

const authStore = useAuthStore()

const colorMode = useColorMode()
const isDark = computed({
  get: () => colorMode.value === 'dark',
  set: (val: boolean) => { colorMode.preference = val ? 'dark' : 'light' },
})

// Fall back to a generic copy if the backend hasn't supplied a message
// (e.g. the response shape changes or maintenance state wasn't loaded).
const message = computed(
  () => authStore.maintenance.message || 'Bingo is undergoing scheduled maintenance.',
)

definePageMeta({
  layout: false,
})
</script>
