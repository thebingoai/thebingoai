<template>
  <div v-if="store.workspaces.length > 1" class="relative">
    <button
      @click="open = !open"
      class="flex items-center gap-2 rounded-lg border border-[var(--line)] px-2.5 py-1.5 text-sm text-gray-700 dark:text-neutral-200 hover:bg-gray-50 dark:hover:bg-neutral-800"
    >
      <span class="truncate max-w-[10rem]">{{ activeName }}</span>
      <span v-if="store.isViewer" class="text-sm rounded bg-gray-100 dark:bg-neutral-700 px-1">viewer</span>
      <ChevronDown class="h-3.5 w-3.5" />
    </button>
    <div v-if="open" class="absolute z-50 mt-1 w-64 rounded-lg border border-[var(--line)] bg-white dark:bg-neutral-800 shadow-lg p-1">
      <button
        v-for="w in store.workspaces"
        :key="w.org_id"
        @click="select(w.org_id)"
        class="flex w-full items-center justify-between gap-2 rounded px-2 py-1.5 text-sm text-left hover:bg-gray-50 dark:hover:bg-neutral-700"
        :class="w.org_id === store.activeOrgId ? 'bg-gray-50 dark:bg-neutral-700' : ''"
      >
        <span class="truncate">{{ w.org_name || w.org_id.slice(0, 8) }}</span>
        <span class="text-sm text-gray-400 dark:text-neutral-500">{{ w.is_home ? 'home' : w.role }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import { useWorkspaceStore } from '~/stores/workspace'

const store = useWorkspaceStore()
const api = useApi()
const open = ref(false)

const activeName = computed(() => {
  const w = store.workspaces.find(w => w.org_id === store.activeOrgId)
  return w ? (w.org_name || w.org_id.slice(0, 8)) : 'Workspace'
})

onMounted(async () => {
  store.hydrate()
  store.reconcile(await api.governance.listWorkspaces())
})

async function select(orgId: string) {
  store.setActive(orgId)
  open.value = false
  // Soft refetch of org-scoped data — NOT a hard reload. A full
  // window.location.reload() re-boots the app and momentarily makes
  // `authStore.isAuthenticated` false (token rehydrates before the user fetch),
  // which the auth middleware turns into a redirect to /login. refreshNuxtData
  // keeps the session intact.
  await refreshNuxtData()
}
</script>
