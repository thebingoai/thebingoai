<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- Page header -->
    <div class="px-7 pt-[18px] pb-4 border-b border-[var(--line)] flex-shrink-0">
      <div class="pr-12">
        <p class="eyebrow mb-0.5 text-gray-400 dark:text-neutral-500">Settings · Reusable prompts</p>
        <h1 class="settings-h1 text-3xl text-gray-900 dark:text-white select-none">Skills</h1>
        <p class="text-sm text-gray-500 dark:text-neutral-400 mt-1.5 max-w-2xl">Skills are reusable, named tasks Bingo can do. Create new ones by asking Bingo in chat — or accept a suggestion below when it spots a repeating pattern.</p>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto p-6">
    <!-- Suggestions Banner -->
    <div v-if="suggestions.length > 0" class="mb-6 rounded-lg border border-purple-200 dark:border-purple-800/50 bg-purple-50 dark:bg-purple-900/20 p-4">
      <h3 class="text-sm font-semibold text-purple-800 dark:text-purple-300 mb-3">
        Suggested skills · {{ suggestions.length }} pattern{{ suggestions.length === 1 ? '' : 's' }} detected
      </h3>
      <div class="flex flex-col gap-2">
        <div
          v-for="suggestion in suggestions"
          :key="suggestion.id"
          class="flex items-start justify-between gap-4 rounded-md bg-white dark:bg-neutral-800 border border-purple-100 dark:border-purple-800/30 px-3 py-2"
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-0.5">
              <p class="text-sm font-medium text-gray-900 dark:text-white truncate font-mono">{{ suggestion.suggested_name }}</p>
              <span class="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300">
                {{ Math.round(suggestion.confidence * 100) }}% match
              </span>
            </div>
            <p v-if="suggestion.pattern_summary" class="text-xs text-gray-500 dark:text-neutral-400 line-clamp-1">{{ suggestion.pattern_summary }}</p>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <button
              type="button"
              :disabled="respondingTo === suggestion.id"
              @click="previewSuggestion(suggestion)"
              class="text-xs font-medium px-2.5 py-1 rounded-md border border-gray-200 dark:border-neutral-600 text-gray-600 dark:text-neutral-300 hover:bg-gray-50 dark:hover:bg-neutral-700 disabled:opacity-50 transition-colors"
            >
              Preview
            </button>
            <button
              type="button"
              :disabled="respondingTo === suggestion.id"
              @click="respondToSuggestion(suggestion.id, 'dismiss')"
              class="text-xs font-medium px-2.5 py-1 rounded-md border border-gray-200 dark:border-neutral-600 text-gray-600 dark:text-neutral-300 hover:bg-gray-50 dark:hover:bg-neutral-700 disabled:opacity-50 transition-colors"
            >
              Dismiss
            </button>
            <button
              type="button"
              :disabled="respondingTo === suggestion.id"
              @click="respondToSuggestion(suggestion.id, 'accept')"
              class="text-xs font-medium px-2.5 py-1 rounded-md bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 transition-colors"
            >
              Create skill
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Section eyebrow + filter buttons -->
    <div v-if="!loading && skills.length > 0" class="flex items-center justify-between mb-3">
      <p class="eyebrow">
        Your skills · {{ activeFilterCount > 0 ? `${filteredSkills.length} of ${skills.length}` : skills.length }}
      </p>
      <div class="flex items-center gap-2">
        <!-- Status filter -->
        <div ref="statusMenuRef" class="relative">
          <button
            type="button"
            @click="showStatusMenu = !showStatusMenu; showCategoryMenu = false"
            class="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md border border-gray-200 dark:border-neutral-600 text-gray-600 dark:text-neutral-300 hover:bg-gray-50 dark:hover:bg-neutral-700 transition-colors"
          >
            <component :is="Filter" class="h-3.5 w-3.5" />
            Filter
            <span v-if="statusFilter !== 'all'" class="flex items-center justify-center h-4 w-4 rounded-full bg-purple-600 text-white text-[10px] font-bold">1</span>
          </button>
          <div
            v-if="showStatusMenu"
            class="absolute right-0 top-full mt-1.5 z-20 min-w-[160px] rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-lg p-3 space-y-1"
          >
            <p class="eyebrow mb-1.5">Status</p>
            <button
              v-for="opt in statusOptions"
              :key="opt.value"
              type="button"
              @click="statusFilter = opt.value; page = 1; showStatusMenu = false"
              class="flex items-center gap-2 w-full text-xs px-2 py-1 rounded-md text-left transition-colors"
              :class="statusFilter === opt.value
                ? 'bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 font-medium'
                : 'text-gray-600 dark:text-neutral-300 hover:bg-gray-50 dark:hover:bg-neutral-700'"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>
        <!-- Type (category) filter -->
        <div ref="categoryMenuRef" class="relative">
          <button
            type="button"
            @click="showCategoryMenu = !showCategoryMenu; showStatusMenu = false"
            class="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md border border-gray-200 dark:border-neutral-600 text-gray-600 dark:text-neutral-300 hover:bg-gray-50 dark:hover:bg-neutral-700 transition-colors"
          >
            <component :is="Tag" class="h-3.5 w-3.5" />
            Filter by category
            <span v-if="typeFilter !== 'all'" class="flex items-center justify-center h-4 w-4 rounded-full bg-purple-600 text-white text-[10px] font-bold">1</span>
          </button>
          <div
            v-if="showCategoryMenu"
            class="absolute right-0 top-full mt-1.5 z-20 min-w-[160px] rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-lg p-3 space-y-1"
          >
            <p class="eyebrow mb-1.5">Type</p>
            <button
              v-for="opt in typeOptions"
              :key="opt.value"
              type="button"
              @click="typeFilter = opt.value; page = 1; showCategoryMenu = false"
              class="flex items-center gap-2 w-full text-xs px-2 py-1 rounded-md text-left transition-colors"
              :class="typeFilter === opt.value
                ? 'bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 font-medium'
                : 'text-gray-600 dark:text-neutral-300 hover:bg-gray-50 dark:hover:bg-neutral-700'"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
      <UiSkeleton class="h-[10.5rem] rounded-lg" />
      <UiSkeleton class="h-[10.5rem] rounded-lg" />
      <UiSkeleton class="h-[10.5rem] rounded-lg" />
      <UiSkeleton class="h-[10.5rem] rounded-lg" />
    </div>

    <!-- Empty State -->
    <UiEmptyState
      v-else-if="skills.length === 0"
      title="No skills yet"
      description="Ask the AI in chat to create a skill for you. For example: 'Create a skill that fetches the current weather'"
      :icon="Wand2"
    />

    <!-- Empty filtered state -->
    <div v-else-if="filteredSkills.length === 0" class="flex flex-col items-center justify-center py-12 text-center">
      <p class="text-sm text-gray-500 dark:text-neutral-400">No skills match the current filters.</p>
      <button type="button" @click="clearFilters" class="mt-2 text-xs text-purple-600 hover:underline">Clear filters</button>
    </div>

    <!-- Skills Grid -->
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
      <UiCard
        v-for="skill in pagedSkills"
        :key="skill.id"
        class="px-4 py-3 min-h-[10.5rem] flex flex-col cursor-pointer hover:shadow-md transition-shadow"
        @click="openDetailDialog(skill)"
      >
        <!-- Icon + Name -->
        <div class="flex items-start gap-2 mb-1.5">
          <component :is="Wand2" class="h-5 w-5 text-purple-500 shrink-0 mt-0.5" />
          <p class="text-base font-semibold text-gray-900 dark:text-white line-clamp-2 leading-snug">{{ formatSkillName(skill.name) }}</p>
        </div>

        <!-- Description -->
        <p v-if="skill.description" class="text-xs text-gray-500 dark:text-neutral-400 line-clamp-3 mb-auto pl-5">{{ skill.description }}</p>
        <div v-else class="mb-auto" />

        <!-- Bottom bar: type indicator + toggle -->
        <div class="flex items-center justify-between mt-3 pt-3 border-t border-gray-100 dark:border-neutral-700">
          <div class="flex items-center gap-1 text-gray-400 dark:text-neutral-500">
            <component :is="skillTypeIcon(skill.skill_type)" class="h-3.5 w-3.5" />
            <span class="text-xs">{{ skillTypeLabel(skill.skill_type).toLowerCase() }}</span>
          </div>

          <button
            type="button"
            :title="skill.is_active ? 'Deactivate skill' : 'Activate skill'"
            @click.stop="handleToggle(skill)"
            class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors"
            :class="skill.is_active ? 'bg-purple-600' : 'bg-gray-200 dark:bg-neutral-600'"
          >
            <span
              class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
              :class="skill.is_active ? 'translate-x-6' : 'translate-x-1'"
            />
          </button>
        </div>
      </UiCard>
    </div>

    <!-- Pagination footer -->
    <div v-if="!loading && pageCount > 1" class="mt-6 flex justify-center items-center gap-1">
      <button
        type="button"
        :disabled="page === 1"
        @click="page = Math.max(1, page - 1)"
        class="px-2 py-1 text-xs rounded-md border border-gray-200 dark:border-neutral-600 text-gray-500 hover:bg-gray-50 dark:hover:bg-neutral-700 disabled:opacity-30 transition-colors"
      >
        ←
      </button>
      <button
        v-for="p in pageCount"
        :key="p"
        type="button"
        @click="page = p"
        class="min-w-[2rem] px-2 py-1 text-xs rounded-md transition-colors"
        :class="p === page
          ? 'bg-gray-900 dark:bg-white text-white dark:text-gray-900 font-medium'
          : 'border border-gray-200 dark:border-neutral-600 text-gray-600 dark:text-neutral-300 hover:bg-gray-50 dark:hover:bg-neutral-700'"
      >
        {{ String(p).padStart(2, '0') }}
      </button>
      <button
        type="button"
        :disabled="page === pageCount"
        @click="page = Math.min(pageCount, page + 1)"
        class="px-2 py-1 text-xs rounded-md border border-gray-200 dark:border-neutral-600 text-gray-500 hover:bg-gray-50 dark:hover:bg-neutral-700 disabled:opacity-30 transition-colors"
      >
        →
      </button>
    </div>

    <!-- Suggestion Preview Dialog -->
    <UiDialog
      v-model:open="showPreviewDialog"
      :title="previewingSuggestion?.suggested_name || 'Suggested skill'"
      size="md"
    >
      <div v-if="previewingSuggestion" class="space-y-3">
        <div class="flex items-center gap-2">
          <UiBadge :variant="skillTypeBadgeVariant(previewingSuggestion.suggested_skill_type)" size="sm">
            {{ skillTypeLabel(previewingSuggestion.suggested_skill_type) }}
          </UiBadge>
          <span class="text-xs text-amber-700 dark:text-amber-300">
            {{ Math.round(previewingSuggestion.confidence * 100) }}% confidence
          </span>
        </div>
        <p v-if="previewingSuggestion.suggested_description" class="text-sm text-gray-600 dark:text-neutral-300">
          {{ previewingSuggestion.suggested_description }}
        </p>
        <div v-if="previewingSuggestion.pattern_summary">
          <p class="text-xs font-medium text-gray-500 mb-1">Detected pattern</p>
          <p class="text-sm text-gray-700 dark:text-neutral-300 italic">{{ previewingSuggestion.pattern_summary }}</p>
        </div>
      </div>

      <template #footer>
        <UiButton variant="outline" @click="showPreviewDialog = false">Close</UiButton>
        <UiButton
          variant="primary"
          :loading="respondingTo === previewingSuggestion?.id"
          @click="acceptFromPreview"
        >
          Create skill
        </UiButton>
      </template>
    </UiDialog>

    <!-- Skill Detail Dialog -->
    <UiDialog
      v-model:open="showDetailDialog"
      :title="viewingSkill?.name || ''"
      size="lg"
    >
      <div v-if="detailLoading" class="space-y-3">
        <UiSkeleton class="h-4 w-1/3 rounded" />
        <UiSkeleton class="h-20 w-full rounded" />
        <UiSkeleton class="h-4 w-1/4 rounded" />
      </div>
      <div v-else-if="skillDetail" class="space-y-4">
        <!-- Type + version -->
        <div class="flex items-center gap-2">
          <UiBadge :variant="skillTypeBadgeVariant(skillDetail.skill_type)" size="sm">
            {{ skillTypeLabel(skillDetail.skill_type) }}
          </UiBadge>
          <span v-if="skillDetail.version > 1" class="text-xs text-gray-400">v{{ skillDetail.version }}</span>
        </div>

        <!-- Description -->
        <div>
          <p class="text-sm text-gray-600">{{ skillDetail.description }}</p>
        </div>

        <!-- Activation hint -->
        <div v-if="skillDetail.activation_hint">
          <p class="text-xs font-medium text-gray-500 mb-1">Activation hint</p>
          <p class="text-sm text-gray-700 italic">{{ skillDetail.activation_hint }}</p>
        </div>

        <!-- Instructions preview -->
        <div v-if="skillDetail.instructions">
          <p class="text-xs font-medium text-gray-500 mb-1">Instructions</p>
          <div class="rounded-md bg-gray-50 border border-gray-200 p-3 text-xs text-gray-700 font-mono whitespace-pre-wrap max-h-40 overflow-y-auto">{{ instructionsPreview(skillDetail.instructions) }}</div>
        </div>

        <!-- Code preview -->
        <div v-if="skillDetail.has_code">
          <p class="text-xs font-medium text-gray-500 mb-1">Code</p>
          <div class="rounded-md bg-gray-900 p-3 text-xs text-green-400 font-mono max-h-32 overflow-y-auto">
            <span class="text-gray-400">async def run(): ...</span>
          </div>
        </div>

        <!-- Prompt template preview -->
        <div v-if="skillDetail.prompt_template">
          <p class="text-xs font-medium text-gray-500 mb-1">Prompt template</p>
          <div class="rounded-md bg-blue-50 border border-blue-100 p-3 text-xs text-gray-700 max-h-32 overflow-y-auto">{{ skillDetail.prompt_template }}</div>
        </div>

        <!-- References -->
        <div v-if="skillDetail.references.length > 0">
          <p class="text-xs font-medium text-gray-500 mb-1">References ({{ skillDetail.references.length }})</p>
          <div class="flex flex-col gap-1">
            <div
              v-for="ref in skillDetail.references"
              :key="ref.id"
              class="flex items-center gap-2 text-xs text-gray-700 px-2 py-1.5 rounded bg-gray-50 border border-gray-100"
            >
              <component :is="FileText" class="h-3.5 w-3.5 text-gray-400 shrink-0" />
              {{ ref.title }}
            </div>
          </div>
        </div>

        <!-- Parameters schema -->
        <div v-if="skillDetail.parameters_schema">
          <p class="text-xs font-medium text-gray-500 mb-1">Parameters</p>
          <div class="rounded-md bg-gray-50 border border-gray-200 p-3 text-xs text-gray-700 font-mono">
            <div v-for="(type, name) in skillDetail.parameters_schema" :key="name" class="flex gap-2">
              <span class="text-blue-600">{{ name }}</span>
              <span class="text-gray-400">{{ type }}</span>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <UiButton variant="danger" @click="openDeleteFromDetail">Delete</UiButton>
        <UiButton variant="outline" @click="showDetailDialog = false">Close</UiButton>
      </template>
    </UiDialog>

    <!-- Delete Confirmation Dialog -->
    <UiDialog
      v-model:open="showDeleteDialog"
      title="Delete Skill"
      size="sm"
    >
      <p class="text-sm text-gray-600">
        Are you sure you want to delete <strong>{{ deletingSkill?.name }}</strong>?
        This action cannot be undone.
      </p>

      <template #footer>
        <UiButton
          variant="outline"
          @click="showDeleteDialog = false"
        >
          Cancel
        </UiButton>
        <UiButton
          variant="danger"
          :loading="deleting"
          @click="confirmDelete"
        >
          Delete
        </UiButton>
      </template>
    </UiDialog>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Wand2, FileText, Filter, Tag, BookOpen, Layers, MessageSquare, Code2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { UserSkill, UserSkillDetail, SkillSuggestion, SkillType } from '~/types/admin'

const api = useApi()

const skills = ref<UserSkill[]>([])
const suggestions = ref<SkillSuggestion[]>([])
const loading = ref(true)

// Detail dialog
const showDetailDialog = ref(false)
const viewingSkill = ref<UserSkill | null>(null)
const skillDetail = ref<UserSkillDetail | null>(null)
const detailLoading = ref(false)

// Delete dialog
const showDeleteDialog = ref(false)
const deletingSkill = ref<UserSkill | null>(null)
const deleting = ref(false)

// Suggestion preview + responding
const showPreviewDialog = ref(false)
const previewingSuggestion = ref<SkillSuggestion | null>(null)
const respondingTo = ref<string | null>(null)

// Filter state
const showStatusMenu = ref(false)
const statusMenuRef = ref<HTMLElement | null>(null)
const showCategoryMenu = ref(false)
const categoryMenuRef = ref<HTMLElement | null>(null)
const statusFilter = ref<'all' | 'active' | 'inactive'>('all')
const typeFilter = ref<SkillType | 'all'>('all')

const statusOptions: { label: string; value: 'all' | 'active' | 'inactive' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Active', value: 'active' },
  { label: 'Inactive', value: 'inactive' },
]

const typeOptions: { label: string; value: SkillType | 'all' }[] = [
  { label: 'All types', value: 'all' },
  { label: 'Instruction', value: 'instruction' },
  { label: 'Hybrid', value: 'hybrid' },
  { label: 'Prompt', value: 'prompt' },
  { label: 'Code', value: 'code' },
]

const activeFilterCount = computed(() => {
  let n = 0
  if (statusFilter.value !== 'all') n++
  if (typeFilter.value !== 'all') n++
  return n
})

function clearFilters() {
  statusFilter.value = 'all'
  typeFilter.value = 'all'
  page.value = 1
}

onClickOutside(statusMenuRef, () => { showStatusMenu.value = false })
onClickOutside(categoryMenuRef, () => { showCategoryMenu.value = false })

// Filtered + paginated skills
const filteredSkills = computed(() => skills.value.filter(s => {
  if (statusFilter.value === 'active' && !s.is_active) return false
  if (statusFilter.value === 'inactive' && s.is_active) return false
  if (typeFilter.value !== 'all' && s.skill_type !== typeFilter.value) return false
  return true
}))

const PAGE_SIZE = 12
const page = ref(1)
const pageCount = computed(() => Math.max(1, Math.ceil(filteredSkills.value.length / PAGE_SIZE)))
const pagedSkills = computed(() =>
  filteredSkills.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE)
)

watch([statusFilter, typeFilter, () => skills.value.length], () => {
  if (page.value > pageCount.value) page.value = Math.max(1, pageCount.value)
})

function previewSuggestion(suggestion: SkillSuggestion) {
  previewingSuggestion.value = suggestion
  showPreviewDialog.value = true
}

async function acceptFromPreview() {
  if (!previewingSuggestion.value) return
  await respondToSuggestion(previewingSuggestion.value.id, 'accept')
  showPreviewDialog.value = false
}

onMounted(async () => {
  await Promise.all([fetchSkills(), fetchSuggestions()])
})

async function fetchSkills() {
  try {
    loading.value = true
    skills.value = await api.skills.list() as UserSkill[]
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to load skills')
  } finally {
    loading.value = false
  }
}

async function fetchSuggestions() {
  try {
    suggestions.value = await api.skills.listSuggestions() as SkillSuggestion[]
  } catch {
    // Suggestions are non-critical — fail silently
  }
}

function skillTypeLabel(type: SkillType | string): string {
  switch (type) {
    case 'instruction': return 'Instruction'
    case 'hybrid': return 'Hybrid'
    case 'prompt': return 'Prompt'
    case 'code': return 'Code'
    default: return 'Code'
  }
}

function skillTypeBadgeVariant(type: SkillType | string): 'default' | 'primary' | 'success' | 'warning' | 'error' | 'info' {
  switch (type) {
    case 'instruction': return 'info'
    case 'hybrid': return 'warning'
    case 'prompt': return 'success'
    case 'code': return 'primary'
    default: return 'default'
  }
}

function skillTypeIcon(type: SkillType | string) {
  switch (type) {
    case 'instruction': return BookOpen
    case 'hybrid': return Layers
    case 'prompt': return MessageSquare
    case 'code': return Code2
    default: return Code2
  }
}

function formatSkillName(raw: string): string {
  return raw
    .replace(/[_-]+/g, ' ')
    .trim()
    .replace(/\b\w/g, c => c.toUpperCase())
}

function openDeleteFromDetail() {
  if (!viewingSkill.value) return
  showDetailDialog.value = false
  openDeleteDialog(viewingSkill.value)
}

function instructionsPreview(instructions: string): string {
  if (instructions.length <= 500) return instructions
  return instructions.slice(0, 500) + '...'
}

async function openDetailDialog(skill: UserSkill) {
  viewingSkill.value = skill
  skillDetail.value = null
  showDetailDialog.value = true
  detailLoading.value = true
  try {
    skillDetail.value = await api.skills.get(skill.id) as UserSkillDetail
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to load skill details')
    showDetailDialog.value = false
  } finally {
    detailLoading.value = false
  }
}

async function handleToggle(skill: UserSkill) {
  try {
    const updated = await api.skills.toggle(skill.id, !skill.is_active) as UserSkill
    const idx = skills.value.findIndex(s => s.id === skill.id)
    if (idx !== -1) {
      skills.value[idx] = updated
    }
    toast.success(updated.is_active ? `${skill.name} activated` : `${skill.name} deactivated`)
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to update skill')
  }
}

function openDeleteDialog(skill: UserSkill) {
  deletingSkill.value = skill
  showDeleteDialog.value = true
}

async function confirmDelete() {
  if (!deletingSkill.value) return

  try {
    deleting.value = true
    await api.skills.remove(deletingSkill.value.id)
    skills.value = skills.value.filter(s => s.id !== deletingSkill.value!.id)
    toast.success(`${deletingSkill.value.name} deleted`)
    showDeleteDialog.value = false
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to delete skill')
  } finally {
    deleting.value = false
  }
}

async function respondToSuggestion(id: string, action: 'accept' | 'dismiss') {
  respondingTo.value = id
  try {
    await api.skills.respondToSuggestion(id, action)
    suggestions.value = suggestions.value.filter(s => s.id !== id)
    if (action === 'accept') {
      toast.success('Skill created from suggestion')
      await fetchSkills()
    } else {
      toast.success('Suggestion dismissed')
    }
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to respond to suggestion')
  } finally {
    respondingTo.value = null
  }
}
</script>
