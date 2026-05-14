<template>
  <div class="flex flex-col h-full overflow-hidden">

    <!-- Page header -->
    <div class="px-7 pt-3 pb-2 border-b border-[var(--line)] flex-shrink-0">
      <p class="eyebrow mb-0.5 text-gray-400 dark:text-neutral-500">Settings · Profile</p>
      <h1 class="settings-h1 text-3xl text-gray-900 dark:text-white mb-1">Profile</h1>
    </div>

    <!-- Scrolling body -->
    <div class="flex-1 overflow-y-auto px-7 py-6 space-y-8">

    <!-- Avatar header card -->
    <UiCard class="p-6">
      <div class="flex items-start gap-5">
        <!-- Avatar circle with ember background -->
        <div
          class="h-16 w-16 rounded-full flex items-center justify-center text-2xl font-semibold text-white shrink-0 select-none"
          :style="{ background: 'var(--ember)' }"
        >
          {{ avatarInitial }}
        </div>

        <div class="flex-1 min-w-0">
          <p class="text-lg font-semibold text-gray-900 dark:text-white">{{ displayName }}</p>
          <p class="text-sm text-gray-500 dark:text-neutral-400">{{ authStore.user?.email }}</p>
          <div class="flex flex-wrap items-center gap-1.5 mt-2">
            <span
              v-for="chip in roleChips"
              :key="chip"
              class="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 dark:bg-neutral-700 text-gray-600 dark:text-neutral-300"
            >
              {{ chip }}
            </span>
            <span v-if="memberSince" class="text-xs text-gray-400 dark:text-neutral-500">
              member since {{ memberSince }}
            </span>
          </div>
        </div>
      </div>
    </UiCard>

    <!-- Identity (read-only until PATCH /api/auth/me exists) -->
    <div class="space-y-4">
      <p class="eyebrow">Identity</p>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-medium text-gray-500 dark:text-neutral-400 mb-1">Display name</label>
          <div class="rounded-lg border border-gray-200 dark:border-neutral-700 px-3 py-2 text-sm text-gray-700 dark:text-neutral-300 bg-gray-50 dark:bg-neutral-800">
            {{ displayName || '—' }}
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 dark:text-neutral-400 mb-1">Email</label>
          <div class="rounded-lg border border-gray-200 dark:border-neutral-700 px-3 py-2 text-sm text-gray-700 dark:text-neutral-300 bg-gray-50 dark:bg-neutral-800">
            {{ authStore.user?.email || '—' }}
          </div>
        </div>
      </div>
    </div>

    <!-- Preferences -->
    <div class="space-y-4">
      <p class="eyebrow">Preferences</p>

      <!-- Appearance: theme swatches -->
      <UiCard class="p-5">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p class="text-sm font-medium text-gray-900 dark:text-white">Appearance</p>
            <p class="text-sm text-gray-500 dark:text-neutral-400 mt-0.5">Paper theme for Bingo's surfaces.</p>
          </div>
          <div class="flex gap-2 shrink-0">
            <button
              v-for="t in appTheme.themes"
              :key="t"
              type="button"
              :title="t"
              @click="appTheme.preference.value = t"
              class="h-7 w-7 rounded-full border-2 transition-all"
              :class="appTheme.preference.value === t
                ? 'border-gray-900 dark:border-white scale-110'
                : 'border-gray-200 dark:border-neutral-600 hover:border-gray-400 dark:hover:border-neutral-400'"
              :style="swatchStyle(t)"
            />
          </div>
        </div>
      </UiCard>

      <!-- Dark mode -->
      <UiCard class="p-5">
        <div class="flex items-center justify-between gap-4">
          <div>
            <p class="text-sm font-medium text-gray-900 dark:text-white">Dark mode</p>
            <p class="text-sm text-gray-500 dark:text-neutral-400 mt-0.5">Override paper theme for dim environments.</p>
          </div>
          <button
            type="button"
            :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
            @click="isDark = !isDark"
            class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors"
            :class="isDark ? 'bg-violet-600' : 'bg-gray-200'"
          >
            <span
              class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
              :class="isDark ? 'translate-x-6' : 'translate-x-1'"
            />
          </button>
        </div>
      </UiCard>
    </div>

    <!-- Danger zone -->
    <div class="rounded-xl border border-red-200 dark:border-red-900/40 bg-red-50/50 dark:bg-red-900/10 p-5">
      <p class="text-sm font-semibold text-red-700 dark:text-red-400 mb-1">Danger zone</p>
      <p class="text-sm text-red-600/80 dark:text-red-400/60 mb-4">Logging out ends your session on this browser.</p>
      <UiButton variant="outline" @click="handleLogout">Log out</UiButton>
    </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const router = useRouter()
const colorMode = useColorMode()
const appTheme = useAppTheme()

const isDark = computed({
  get: () => colorMode.value === 'dark',
  set: (val: boolean) => { colorMode.preference = val ? 'dark' : 'light' },
})

const avatarInitial = computed(() => {
  const name = (authStore.user as any)?.name || authStore.user?.email || '?'
  return name.charAt(0).toUpperCase()
})

const displayName = computed(() =>
  (authStore.user as any)?.name || authStore.user?.email?.split('@')[0] || ''
)

const roleChips = computed((): string[] => {
  const u = authStore.user as any
  const all: string[] = []
  if (Array.isArray(u?.roles)) all.push(...u.roles)
  if (u?.role) all.push(u.role)
  return [...new Set(all)]
})

const memberSince = computed(() => {
  const d = (authStore.user as any)?.created_at
  if (!d) return null
  return new Date(d).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
})

const SWATCH_COLORS: Record<string, string> = {
  kraft: '#fafafa',
  cool: '#f3f4ff',
  ink: '#f1edea',
}

function swatchStyle(theme: string): Record<string, string> {
  return { background: SWATCH_COLORS[theme] ?? '#fafafa' }
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>
