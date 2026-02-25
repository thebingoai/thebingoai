<template>
  <div class="p-6">
    <div class="mb-6">
      <h2 class="text-2xl font-medium text-gray-900">Skills</h2>
      <p class="text-sm text-gray-500 mt-1">Manage your custom skills. Create new skills by asking the AI in chat.</p>
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
          <UiBadge v-if="skill.has_prompt_template" variant="default" size="sm">Prompt</UiBadge>
          <UiBadge v-if="skill.has_code" variant="default" size="sm">Code</UiBadge>
        </div>

        <!-- Bottom bar: toggle + delete -->
        <div class="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
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
import { Wand2, Trash2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { UserSkill } from '~/types/admin'

const api = useApi()

const skills = ref<UserSkill[]>([])
const loading = ref(true)
const showDeleteDialog = ref(false)
const deletingSkill = ref<UserSkill | null>(null)
const deleting = ref(false)

onMounted(async () => {
  await fetchSkills()
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
</script>
