<template>
  <div class="relative isolate min-h-screen flex items-center justify-center overflow-hidden bg-[#FAFAF7] dark:bg-[#0E0E10]">
    <MaintenanceTileBackground class="absolute inset-0 -z-10" :card-el="cardEl" />

    <!-- Dark mode toggle (top right) -->
    <button
      class="absolute top-4 right-4 z-20 p-2 rounded-lg text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200 hover:bg-neutral-100/60 dark:hover:bg-neutral-800/60 transition-colors"
      :aria-label="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
      @click="isDark = !isDark"
    >
      <Sun v-if="isDark" class="h-4 w-4" />
      <Moon v-else class="h-4 w-4" />
    </button>

    <div
      ref="cardEl"
      class="relative z-10 w-[min(94vw,42rem)] bg-white/70 dark:bg-[#0E0E10]/70 backdrop-blur-2xl backdrop-saturate-[1.1] rounded-[20px] shadow-[0_40px_80px_-24px_rgba(110,72,157,0.18)] dark:shadow-[0_40px_80px_-24px_rgba(110,72,157,0.35)] ring-1 ring-black/5 dark:ring-white/10 px-16 py-20 text-center"
    >
      <div class="flex justify-center">
        <img src="/logo/BINGO Logo Design_FA_Primary.png" alt="Bingo" class="h-12 w-auto mb-10 dark:hidden" />
        <img src="/logo/BINGO Logo Design_FA_Primary_W.png" alt="Bingo" class="h-12 w-auto mb-10 hidden dark:block" />
      </div>

      <h1 class="font-display text-[3rem] leading-[1.05] tracking-[-0.02em] text-neutral-900 dark:text-neutral-50 mb-6">
        We'll be back <span class="italic">shortly.</span>
      </h1>

      <p class="mx-auto max-w-md text-[1rem] leading-relaxed text-neutral-600 dark:text-neutral-400">
        {{ message }}
      </p>
    </div>
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

const cardEl = ref<HTMLElement | null>(null)

definePageMeta({
  layout: false,
})
</script>
