<template>
  <div class="p-6">
    <h2 class="text-2xl font-medium text-gray-900 dark:text-white mb-6">Profile</h2>

    <UiCard class="p-6">
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-extralight text-gray-700 dark:text-neutral-400 mb-1">Email</label>
          <div class="text-gray-900 dark:text-white">{{ authStore.user?.email }}</div>
        </div>

        <div>
          <label class="block text-sm font-extralight text-gray-700 dark:text-neutral-400 mb-1">Member Since</label>
          <div class="text-gray-900 dark:text-white">{{ formatDate(authStore.user?.created_at) }}</div>
        </div>

        <div class="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-neutral-700">
          <label class="text-sm font-extralight text-gray-700 dark:text-neutral-400">Dark Mode</label>
          <button
            type="button"
            :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
            @click="isDark = !isDark"
            class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors"
            :class="isDark ? 'bg-blue-600' : 'bg-gray-200'"
          >
            <span
              class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
              :class="isDark ? 'translate-x-6' : 'translate-x-1'"
            />
          </button>
        </div>

        <div class="pt-2 border-t border-gray-200 dark:border-neutral-700">
          <UiButton variant="danger" @click="handleLogout">
            Logout
          </UiButton>
        </div>
      </div>
    </UiCard>
  </div>
</template>

<script setup lang="ts">
import { parseUtcDate } from '~/utils/format'

const authStore = useAuthStore()
const router = useRouter()
const colorMode = useColorMode()

const isDark = computed({
  get: () => colorMode.value === 'dark',
  set: (val: boolean) => { colorMode.preference = val ? 'dark' : 'light' }
})

const formatDate = (dateString?: string) => {
  if (!dateString) return 'Unknown'
  return parseUtcDate(dateString).toLocaleDateString()
}

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>
