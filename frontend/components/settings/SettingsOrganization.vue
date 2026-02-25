<template>
  <div class="p-6">
    <div class="mb-6">
      <h2 class="text-2xl font-medium text-gray-900">Organization</h2>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-4">
      <UiSkeleton class="h-20 w-full rounded-lg" />
      <div class="flex flex-wrap gap-4">
        <UiSkeleton class="h-32 w-48 rounded-lg" />
        <UiSkeleton class="h-32 w-48 rounded-lg" />
      </div>
    </div>

    <!-- No org -->
    <UiEmptyState
      v-else-if="!org"
      title="No organization found"
      description="Your account is not linked to an organization."
      :icon="Building2"
    />

    <template v-else>
      <!-- Org info card -->
      <UiCard class="p-5 mb-6 max-w-sm">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100">
            <Building2 class="h-5 w-5 text-gray-600" />
          </div>
          <div>
            <p class="font-medium text-gray-900">{{ org.name }}</p>
            <p class="text-xs text-gray-400">{{ teams.length }} team{{ teams.length !== 1 ? 's' : '' }}</p>
          </div>
        </div>
      </UiCard>

      <!-- Teams section -->
      <div class="mb-4 flex items-center justify-between">
        <h3 class="text-base font-medium text-gray-900">Teams</h3>
        <UiButton size="sm" @click="showCreateDialog = true">
          <Plus class="h-3.5 w-3.5" />
          Create Team
        </UiButton>
      </div>

      <!-- Teams grid -->
      <div class="flex flex-wrap gap-4">
        <UiCard
          v-for="team in teams"
          :key="team.id"
          class="p-5 w-48 h-32"
        >
          <div class="flex flex-col h-full">
            <div class="flex items-center gap-2">
              <Users class="h-4 w-4 text-gray-400 shrink-0" />
              <p class="text-sm font-medium text-gray-900 truncate">{{ team.name }}</p>
            </div>
            <p class="mt-auto text-xs text-gray-400">ID: {{ team.id.slice(0, 8) }}…</p>
          </div>
        </UiCard>

        <!-- Empty state in grid -->
        <div
          v-if="teams.length === 0"
          class="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-gray-300 rounded-lg w-48 h-32 text-gray-400"
        >
          <Users class="h-5 w-5" />
          <span class="text-xs">No teams yet</span>
        </div>
      </div>
    </template>

    <!-- Create Team Dialog -->
    <UiDialog v-model:open="showCreateDialog" title="Create Team" size="sm">
      <UiInput
        v-model="newTeamName"
        label="Team Name"
        placeholder="Engineering"
        :error="createError"
        @keydown.enter="handleCreateTeam"
      />

      <template #footer>
        <UiButton variant="outline" @click="showCreateDialog = false">Cancel</UiButton>
        <UiButton :loading="creating" @click="handleCreateTeam">Create Team</UiButton>
      </template>
    </UiDialog>
  </div>
</template>

<script setup lang="ts">
import { Building2, Users, Plus } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { Organization, Team } from '~/types/admin'
import { useAuthStore } from '~/stores/auth'

const api = useApi()
const authStore = useAuthStore()

const loading = ref(true)
const org = ref<Organization | null>(null)
const teams = ref<Team[]>([])
const showCreateDialog = ref(false)
const newTeamName = ref('')
const createError = ref('')
const creating = ref(false)

onMounted(async () => {
  await fetchOrg()
})

async function fetchOrg() {
  const orgId = authStore.user?.org_id
  if (!orgId) {
    loading.value = false
    return
  }

  try {
    loading.value = true
    const [orgData, teamsData] = await Promise.all([
      api.orgs.get(orgId) as Promise<Organization>,
      api.orgs.getTeams(orgId) as Promise<Team[]>
    ])
    org.value = orgData
    teams.value = teamsData
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to load organization')
  } finally {
    loading.value = false
  }
}

async function handleCreateTeam() {
  createError.value = ''
  if (!newTeamName.value.trim()) {
    createError.value = 'Team name is required'
    return
  }

  const orgId = authStore.user?.org_id
  if (!orgId) return

  try {
    creating.value = true
    await api.orgs.createTeam(orgId, newTeamName.value.trim())
    toast.success('Team created successfully')
    showCreateDialog.value = false
    newTeamName.value = ''
    await fetchOrg()
  } catch (err: any) {
    const msg = err?.data?.detail || err?.message || 'Failed to create team'
    toast.error(msg)
  } finally {
    creating.value = false
  }
}
</script>
