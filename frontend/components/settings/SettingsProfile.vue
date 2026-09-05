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
      <p class="text-sm font-medium tracking-[0.12em] uppercase text-[var(--ink-2)]">Identity</p>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-500 dark:text-neutral-400 mb-1">Display name</label>
          <div class="rounded-lg border border-gray-200 dark:border-neutral-700 px-3 py-2 text-sm text-gray-700 dark:text-neutral-300 bg-gray-50 dark:bg-neutral-800">
            {{ displayName || '—' }}
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-500 dark:text-neutral-400 mb-1">Email</label>
          <div class="rounded-lg border border-gray-200 dark:border-neutral-700 px-3 py-2 text-sm text-gray-700 dark:text-neutral-300 bg-gray-50 dark:bg-neutral-800">
            {{ authStore.user?.email || '—' }}
          </div>
        </div>
      </div>
    </div>

    <!-- Preferences -->
    <div class="space-y-4">
      <p class="text-sm font-medium tracking-[0.12em] uppercase text-[var(--ink-2)]">Preferences</p>

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

      <!-- Text size -->
      <UiCard class="p-5">
        <div class="flex items-center justify-between gap-4">
          <div>
            <p class="text-sm font-medium text-gray-900 dark:text-white">Text size</p>
            <p class="text-sm text-gray-500 dark:text-neutral-400 mt-0.5">Adjust the size of text across Bingo.</p>
          </div>
          <div class="flex gap-1 shrink-0 rounded-lg border border-gray-200 dark:border-neutral-700 p-0.5">
            <button
              v-for="opt in FONT_SIZE_OPTIONS"
              :key="opt.value"
              type="button"
              @click="fontSize.preference.value = opt.value"
              class="px-3 py-1 rounded-md text-sm font-medium transition-colors"
              :class="fontSize.preference.value === opt.value
                ? 'bg-gray-900 text-white dark:bg-white dark:text-gray-900'
                : 'text-gray-600 dark:text-neutral-300 hover:bg-gray-100 dark:hover:bg-neutral-700'"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>
      </UiCard>

      <!-- Auto-memory: the Memory section is hidden from the nav, and the daily
           memory task treats a missing preference as enabled, so the opt-out
           needs a visible home. Everything else about memories lives on the
           (still routable) Memory page. -->
      <UiCard class="p-5">
        <div class="flex items-center justify-between gap-4">
          <div>
            <p class="text-sm font-medium text-gray-900 dark:text-white">Auto conversation memory</p>
            <p class="text-sm text-gray-500 dark:text-neutral-400 mt-0.5">
              Bingo summarizes your daily chats so future ones build on past context.
              <!-- Viewers see only the Account sections, so ?tab=memory would
                   fall back to the current pane for them. -->
              <NuxtLink v-if="!workspace.isViewer" to="/settings?tab=memory" class="underline underline-offset-2 hover:text-gray-900 dark:hover:text-white">Manage memories →</NuxtLink>
            </p>
          </div>
          <button
            type="button"
            :title="memoryEnabled ? 'Disable auto-memory' : 'Enable auto-memory'"
            :disabled="memoryBusy"
            @click="toggleMemoryEnabled"
            class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50"
            :class="memoryEnabled ? 'bg-violet-600' : 'bg-gray-200 dark:bg-neutral-600'"
          >
            <span
              class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
              :class="memoryEnabled ? 'translate-x-6' : 'translate-x-1'"
            />
          </button>
        </div>
      </UiCard>
    </div>

    <!-- Danger zone -->
    <div class="rounded-xl border border-red-200 dark:border-red-900/40 bg-red-50/50 dark:bg-red-900/10 p-5">
      <p class="text-sm font-semibold text-red-700 dark:text-red-400 mb-1">Danger zone</p>
      <p class="text-sm text-red-600/80 dark:text-red-400/60 mb-4">Logging out ends your session on this browser. Deleting your account is permanent.</p>
      <div class="flex gap-3">
        <UiButton variant="outline" @click="handleLogout">Log out</UiButton>
        <UiButton variant="danger" @click="showDeleteDialog = true">Delete account</UiButton>
      </div>
    </div>
    </div>

    <!-- Delete account confirmation -->
    <UiDialog v-model:open="showDeleteDialog" title="Delete account" size="sm">
      <p class="text-sm text-gray-600 dark:text-neutral-300">
        Permanently delete <strong>{{ authStore.user?.email }}</strong>? Your login is
        disabled and you're signed out. This cannot be undone.
      </p>
      <template #footer>
        <UiButton variant="outline" @click="showDeleteDialog = false">Cancel</UiButton>
        <UiButton variant="danger" :loading="deleting" @click="confirmDelete">Delete account</UiButton>
      </template>
    </UiDialog>
  </div>
</template>

<script setup lang="ts">
import { toast } from 'vue-sonner'

const authStore = useAuthStore()
const workspace = useWorkspaceStore()
const router = useRouter()
const colorMode = useColorMode()
const appTheme = useAppTheme()
const fontSize = useAppFontSize()

const FONT_SIZE_OPTIONS = [
  { value: 'sm' as const, label: 'Small' },
  { value: 'md' as const, label: 'Medium' },
  { value: 'lg' as const, label: 'Large' },
]

const showDeleteDialog = ref(false)
const deleting = ref(false)

const api = useApi() as any
const memoryEnabled = ref(true)   // matches the backend's default for a missing preference
// Busy while the stored value is loading or a save is in flight. Starting
// busy keeps the switch inert until the GET settles, so a late response
// cannot land after a save and show the opposite of what was persisted.
const memoryBusy = ref(true)

onMounted(async () => {
  try {
    memoryEnabled.value = (await api.memory.getSettings()).memory_enabled
  } catch {
    // Keep the default; the switch still writes.
  } finally {
    memoryBusy.value = false
  }
})

async function toggleMemoryEnabled() {
  try {
    memoryBusy.value = true
    const updated = await api.memory.updateSettings(!memoryEnabled.value)
    memoryEnabled.value = updated.memory_enabled
    toast.success(updated.memory_enabled ? 'Auto-memory enabled' : 'Auto-memory disabled')
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to update settings')
  } finally {
    memoryBusy.value = false
  }
}

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

async function confirmDelete() {
  deleting.value = true
  try {
    await authStore.deleteAccount()
    toast.success('Account deleted')
    showDeleteDialog.value = false
    router.push('/login')
  } catch (err: any) {
    toast.error(err?.data?.detail?.message || err?.data?.detail || err?.message || 'Failed to delete account')
  } finally {
    deleting.value = false
  }
}
</script>
