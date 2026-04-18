<template>
  <div class="p-6 space-y-8">
    <!-- Page header -->
    <div>
      <h2 class="text-2xl font-medium text-gray-900 dark:text-white">Memory</h2>
      <p class="text-sm text-gray-500 dark:text-neutral-400 mt-1">Control what the AI remembers about you across conversations.</p>
    </div>

    <!-- Section 1: Daily Conversation Memory -->
    <UiCard class="p-5">
      <div class="flex items-start justify-between gap-4">
        <div class="space-y-1">
          <p class="text-sm font-medium text-gray-900 dark:text-white">Daily Conversation Memory</p>
          <p class="text-sm text-gray-500 dark:text-neutral-400">Automatically summarizes your daily conversations for future context.</p>
        </div>
        <button
          type="button"
          :title="memoryEnabled ? 'Disable auto-memory' : 'Enable auto-memory'"
          :disabled="savingSettings"
          @click="toggleMemoryEnabled"
          class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50"
          :class="memoryEnabled ? 'bg-blue-600' : 'bg-gray-200'"
        >
          <span
            class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
            :class="memoryEnabled ? 'translate-x-6' : 'translate-x-1'"
          />
        </button>
      </div>

      <div class="mt-4 pt-4 border-t border-gray-100 dark:border-neutral-700 flex justify-end">
        <UiButton
          variant="outline"
          size="sm"
          @click="showDeleteAllDialog = true"
        >
          Delete Conversation Memories
        </UiButton>
      </div>

      <!-- Activity heatmap -->
      <div class="mt-4 pt-4 border-t border-gray-100 dark:border-neutral-700">
        <div class="flex items-center justify-between mb-3">
          <p class="text-xs font-medium text-gray-700 dark:text-neutral-300">Conversation Activity</p>
          <p v-if="!heatmapLoading && heatmapTotalConversations > 0" class="text-xs text-gray-400 dark:text-neutral-500">
            {{ heatmapTotalConversations }} conversations · {{ heatmapTotalDays }} days recorded
          </p>
        </div>
        <UiContributionHeatmap :data="heatmapDataMap" :loading="heatmapLoading" />
      </div>
    </UiCard>

    <!-- Section 2: Custom Memories -->
    <div>
      <div class="flex items-center justify-between mb-4">
        <div>
          <h3 class="text-base font-medium text-gray-900 dark:text-white">Custom Memories</h3>
          <p class="text-sm text-gray-500 dark:text-neutral-400 mt-0.5">Facts and preferences the AI should always know about you.</p>
        </div>
        <UiButton
          size="sm"
          @click="openAddDialog"
          :disabled="entries.length >= 50"
        >
          Add Memory
        </UiButton>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="space-y-2">
        <UiSkeleton class="h-14 w-full rounded-lg" />
        <UiSkeleton class="h-14 w-full rounded-lg" />
        <UiSkeleton class="h-14 w-full rounded-lg" />
      </div>

      <!-- Empty -->
      <UiEmptyState
        v-else-if="entries.length === 0"
        title="No custom memories"
        description="Add facts or preferences you'd like the AI to always remember — like your name, role, or working style."
        :icon="Brain"
      />

      <!-- List -->
      <div v-else class="space-y-2">
        <div
          v-for="entry in entries"
          :key="entry.id"
          class="flex items-center gap-3 rounded-lg border border-gray-200 dark:border-neutral-700 px-4 py-3"
        >
          <!-- Active toggle -->
          <button
            type="button"
            :title="entry.is_active ? 'Deactivate' : 'Activate'"
            @click="toggleEntry(entry)"
            class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors"
            :class="entry.is_active ? 'bg-blue-600' : 'bg-gray-200'"
          >
            <span
              class="inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform"
              :class="entry.is_active ? 'translate-x-4' : 'translate-x-0.5'"
            />
          </button>

          <!-- Content -->
          <div class="flex-1 min-w-0">
            <p class="text-sm text-gray-900 dark:text-neutral-200 truncate" :class="!entry.is_active && 'opacity-50'">{{ entry.content }}</p>
            <UiBadge v-if="entry.category" variant="default" size="sm" class="mt-0.5">{{ entry.category }}</UiBadge>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-1 shrink-0">
            <button
              type="button"
              title="Edit"
              @click="openEditDialog(entry)"
              class="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <Pencil class="h-4 w-4" />
            </button>
            <button
              type="button"
              title="Delete"
              @click="openDeleteEntryDialog(entry)"
              class="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors"
            >
              <Trash2 class="h-4 w-4" />
            </button>
          </div>
        </div>

        <p v-if="entries.length >= 50" class="text-xs text-gray-400 text-center pt-1">
          Memory limit reached (50 entries). Delete some to add more.
        </p>
      </div>
    </div>

    <!-- Add/Edit Dialog -->
    <UiDialog
      v-model:open="showEntryDialog"
      :title="editingEntry ? 'Edit Memory' : 'Add Memory'"
      size="sm"
    >
      <div class="space-y-3">
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-neutral-300 mb-1">Content</label>
          <textarea
            v-model="entryForm.content"
            rows="3"
            placeholder="e.g. Always respond in bullet points"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none dark:bg-neutral-700 dark:border-neutral-600 dark:text-neutral-100 dark:placeholder-neutral-500 dark:focus:border-blue-400"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-neutral-300 mb-1">Category <span class="text-gray-400 dark:text-neutral-500 font-normal">(optional)</span></label>
          <input
            v-model="entryForm.category"
            type="text"
            placeholder="e.g. Formatting, Background, Preferences"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:bg-neutral-700 dark:border-neutral-600 dark:text-neutral-100 dark:placeholder-neutral-500 dark:focus:border-blue-400"
          />
        </div>
      </div>

      <template #footer>
        <UiButton variant="outline" @click="showEntryDialog = false">Cancel</UiButton>
        <UiButton
          :loading="savingEntry"
          :disabled="!entryForm.content.trim()"
          @click="saveEntry"
        >
          {{ editingEntry ? 'Save' : 'Add' }}
        </UiButton>
      </template>
    </UiDialog>

    <!-- Delete Entry Dialog -->
    <UiDialog
      v-model:open="showDeleteEntryDialog"
      title="Delete Memory"
      size="sm"
    >
      <p class="text-sm text-gray-600">
        Are you sure you want to delete this memory? This action cannot be undone.
      </p>
      <template #footer>
        <UiButton variant="outline" @click="showDeleteEntryDialog = false">Cancel</UiButton>
        <UiButton variant="danger" :loading="deletingEntry" @click="confirmDeleteEntry">Delete</UiButton>
      </template>
    </UiDialog>

    <!-- Delete Conversation Memories Dialog -->
    <UiDialog
      v-model:open="showDeleteAllDialog"
      title="Delete Conversation Memories"
      size="sm"
    >
      <p class="text-sm text-gray-600">
        This will permanently delete all daily conversation memories. This action cannot be undone.
      </p>
      <template #footer>
        <UiButton variant="outline" @click="showDeleteAllDialog = false">Cancel</UiButton>
        <UiButton variant="danger" :loading="deletingAll" @click="confirmDeleteAll">Delete All</UiButton>
      </template>
    </UiDialog>
  </div>
</template>

<script setup lang="ts">
import { Brain, Pencil, Trash2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { UserMemoryEntry, MemorySettings, MemoryHeatmapResponse } from '~/types/memory'

const api = useApi()

// ── State ────────────────────────────────────────────────────────────────────

const entries = ref<UserMemoryEntry[]>([])
const loading = ref(true)
const memoryEnabled = ref(true)
const savingSettings = ref(false)

const showEntryDialog = ref(false)
const editingEntry = ref<UserMemoryEntry | null>(null)
const savingEntry = ref(false)
const entryForm = reactive({ content: '', category: '' })

const showDeleteEntryDialog = ref(false)
const deletingEntryTarget = ref<UserMemoryEntry | null>(null)
const deletingEntry = ref(false)

const showDeleteAllDialog = ref(false)
const deletingAll = ref(false)

const heatmapLoading = ref(true)
const heatmapDataMap = ref(new Map<string, number>())
const heatmapTotalDays = ref(0)
const heatmapTotalConversations = ref(0)

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  await Promise.all([fetchEntries(), fetchSettings(), fetchHeatmap()])
})

// ── Fetch ─────────────────────────────────────────────────────────────────────

async function fetchEntries() {
  try {
    loading.value = true
    const res = await api.memory.listEntries() as { entries: UserMemoryEntry[]; total: number }
    entries.value = res.entries
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to load memories')
  } finally {
    loading.value = false
  }
}

async function fetchSettings() {
  try {
    const res = await api.memory.getSettings() as MemorySettings
    memoryEnabled.value = res.memory_enabled
  } catch {
    // silently ignore — default to true
  }
}

async function fetchHeatmap() {
  try {
    heatmapLoading.value = true
    const res = await api.memory.heatmap() as MemoryHeatmapResponse
    const map = new Map<string, number>()
    for (const entry of res.data) {
      map.set(entry.date, entry.count)
    }
    heatmapDataMap.value = map
    heatmapTotalDays.value = res.total_days
    heatmapTotalConversations.value = res.total_conversations
  } catch {
    // silently ignore — heatmap remains empty
  } finally {
    heatmapLoading.value = false
  }
}

// ── Settings ──────────────────────────────────────────────────────────────────

async function toggleMemoryEnabled() {
  try {
    savingSettings.value = true
    const updated = await api.memory.updateSettings(!memoryEnabled.value) as MemorySettings
    memoryEnabled.value = updated.memory_enabled
    toast.success(updated.memory_enabled ? 'Auto-memory enabled' : 'Auto-memory disabled')
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to update settings')
  } finally {
    savingSettings.value = false
  }
}

// ── Custom memory CRUD ────────────────────────────────────────────────────────

function openAddDialog() {
  editingEntry.value = null
  entryForm.content = ''
  entryForm.category = ''
  showEntryDialog.value = true
}

function openEditDialog(entry: UserMemoryEntry) {
  editingEntry.value = entry
  entryForm.content = entry.content
  entryForm.category = entry.category || ''
  showEntryDialog.value = true
}

async function saveEntry() {
  if (!entryForm.content.trim()) return
  try {
    savingEntry.value = true
    if (editingEntry.value) {
      const updated = await api.memory.updateEntry(editingEntry.value.id, {
        content: entryForm.content.trim(),
        category: entryForm.category.trim() || null,
      }) as UserMemoryEntry
      const idx = entries.value.findIndex(e => e.id === editingEntry.value!.id)
      if (idx !== -1) entries.value[idx] = updated
      toast.success('Memory updated')
    } else {
      const created = await api.memory.createEntry(
        entryForm.content.trim(),
        entryForm.category.trim() || undefined,
      ) as UserMemoryEntry
      entries.value.unshift(created)
      toast.success('Memory added')
    }
    showEntryDialog.value = false
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to save memory')
  } finally {
    savingEntry.value = false
  }
}

async function toggleEntry(entry: UserMemoryEntry) {
  try {
    const updated = await api.memory.updateEntry(entry.id, { is_active: !entry.is_active }) as UserMemoryEntry
    const idx = entries.value.findIndex(e => e.id === entry.id)
    if (idx !== -1) entries.value[idx] = updated
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to update memory')
  }
}

function openDeleteEntryDialog(entry: UserMemoryEntry) {
  deletingEntryTarget.value = entry
  showDeleteEntryDialog.value = true
}

async function confirmDeleteEntry() {
  if (!deletingEntryTarget.value) return
  try {
    deletingEntry.value = true
    await api.memory.deleteEntry(deletingEntryTarget.value.id)
    entries.value = entries.value.filter(e => e.id !== deletingEntryTarget.value!.id)
    toast.success('Memory deleted')
    showDeleteEntryDialog.value = false
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to delete memory')
  } finally {
    deletingEntry.value = false
  }
}

// ── Delete all auto-memories ──────────────────────────────────────────────────

async function confirmDeleteAll() {
  try {
    deletingAll.value = true
    await api.memory.deleteAll()
    toast.success('All conversation memories deleted')
    showDeleteAllDialog.value = false
    fetchHeatmap()
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to delete memories')
  } finally {
    deletingAll.value = false
  }
}
</script>
