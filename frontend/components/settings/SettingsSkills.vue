<template>
  <div class="p-6">
    <div class="mb-6">
      <h2 class="text-2xl font-medium text-gray-900">Skills</h2>
      <p class="text-sm text-gray-500 mt-1">Manage your custom skills. Create new skills by asking the AI in chat.</p>
    </div>

    <!-- Suggestions Banner -->
    <div v-if="suggestions.length > 0" class="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4">
      <h3 class="text-sm font-semibold text-amber-800 mb-3">Suggested Skills</h3>
      <p class="text-xs text-amber-700 mb-3">Background analysis detected these repeated patterns. Accept to create a skill automatically.</p>
      <div class="flex flex-col gap-2">
        <div
          v-for="suggestion in suggestions"
          :key="suggestion.id"
          class="flex items-start justify-between gap-4 rounded-md bg-white border border-amber-100 px-3 py-2.5"
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-0.5">
              <p class="text-sm font-medium text-gray-900 truncate">{{ suggestion.suggested_name }}</p>
              <span class="shrink-0 text-xs font-medium px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700">
                {{ Math.round(suggestion.confidence * 100) }}% match
              </span>
            </div>
            <p v-if="suggestion.pattern_summary" class="text-xs text-gray-500 line-clamp-2">{{ suggestion.pattern_summary }}</p>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <button
              type="button"
              :disabled="respondingTo === suggestion.id"
              @click="respondToSuggestion(suggestion.id, 'accept')"
              class="text-xs font-medium px-2.5 py-1 rounded-md bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50 transition-colors"
            >
              Create
            </button>
            <button
              type="button"
              :disabled="respondingTo === suggestion.id"
              @click="respondToSuggestion(suggestion.id, 'dismiss')"
              class="text-xs font-medium px-2.5 py-1 rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex flex-wrap gap-4">
      <UiSkeleton class="h-56 w-56 rounded-lg" />
      <UiSkeleton class="h-56 w-56 rounded-lg" />
      <UiSkeleton class="h-56 w-56 rounded-lg" />
    </div>

    <!-- Empty State -->
    <UiEmptyState
      v-else-if="skills.length === 0"
      title="No skills yet"
      description="Ask the AI in chat to create a skill for you. For example: 'Create a skill that fetches the current weather'"
      :icon="Wand2"
    />

    <!-- Skills Grid -->
    <div v-else class="flex flex-wrap gap-4">
      <UiCard
        v-for="skill in skills"
        :key="skill.id"
        class="px-5 py-4 h-56 w-56 flex flex-col"
      >
        <!-- Icon + Name -->
        <div class="flex items-start gap-2 mb-2">
          <component :is="Wand2" class="h-5 w-5 text-purple-500 shrink-0 mt-0.5" />
          <p class="text-sm font-medium text-gray-900 line-clamp-2 leading-snug">{{ skill.name }}</p>
        </div>

        <!-- Description -->
        <p class="text-xs text-gray-500 line-clamp-3 mb-2">{{ skill.description }}</p>

        <!-- Badges -->
        <div class="flex flex-wrap gap-1 mb-auto">
          <UiBadge :variant="skillTypeBadgeVariant(skill.skill_type)" size="sm">
            {{ skillTypeLabel(skill.skill_type) }}
          </UiBadge>
          <UiBadge v-if="skill.reference_count > 0" variant="default" size="sm">
            {{ skill.reference_count }} ref{{ skill.reference_count !== 1 ? 's' : '' }}
          </UiBadge>
          <UiBadge v-if="skill.version > 1" variant="default" size="sm">
            v{{ skill.version }}
          </UiBadge>
        </div>

        <!-- Bottom bar: view + toggle + delete -->
        <div class="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
          <div class="flex items-center gap-1.5">
            <button
              type="button"
              title="View skill details"
              @click="openDetailDialog(skill)"
              class="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <component :is="Eye" class="h-4 w-4" />
            </button>

            <button
              type="button"
              :title="skill.is_active ? 'Deactivate skill' : 'Activate skill'"
              @click="handleToggle(skill)"
              class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors"
              :class="skill.is_active ? 'bg-blue-600' : 'bg-gray-200'"
            >
              <span
                class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                :class="skill.is_active ? 'translate-x-6' : 'translate-x-1'"
              />
            </button>
          </div>

          <button
            type="button"
            title="Delete skill"
            @click="openDeleteDialog(skill)"
            class="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors"
          >
            <component :is="Trash2" class="h-4 w-4" />
          </button>
        </div>
      </UiCard>
    </div>

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
</template>

<script setup lang="ts">
import { Wand2, Trash2, Eye, FileText } from 'lucide-vue-next'
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

// Suggestion responding
const respondingTo = ref<string | null>(null)

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
