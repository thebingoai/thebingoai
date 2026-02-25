<template>
  <div class="p-6">
    <div class="mb-6">
      <h2 class="text-2xl font-medium text-gray-900">Team</h2>
    </div>

    <!-- Loading -->
    <div v-if="loadingTeams" class="space-y-3">
      <UiSkeleton class="h-10 w-64 rounded-lg" />
      <UiSkeleton class="h-16 w-full rounded-lg" />
      <UiSkeleton class="h-16 w-full rounded-lg" />
    </div>

    <template v-else-if="teams.length > 0">
      <!-- Team selector -->
      <div class="mb-6 flex items-center gap-4">
        <UiSelect
          v-if="teams.length > 1"
          v-model="selectedTeamId"
          :options="teamOptions"
          label="Select Team"
          class="w-64"
        />
        <div v-else class="flex items-center gap-2">
          <Users class="h-4 w-4 text-gray-400" />
          <span class="text-sm font-medium text-gray-900">{{ teams[0]?.name }}</span>
        </div>

        <UiButton size="sm" class="ml-auto" @click="showAddDialog = true">
          <UserPlus class="h-3.5 w-3.5" />
          Add Member
        </UiButton>
      </div>

      <!-- Members list -->
      <div v-if="loadingMembers" class="space-y-3">
        <UiSkeleton class="h-14 w-full rounded-lg" v-for="i in 3" :key="i" />
      </div>

      <UiEmptyState
        v-else-if="members.length === 0"
        title="No members"
        description="This team has no members yet."
        :icon="Users"
      >
        <template #action>
          <UiButton size="sm" @click="showAddDialog = true">Add Member</UiButton>
        </template>
      </UiEmptyState>

      <div v-else class="space-y-2">
        <div
          v-for="member in members"
          :key="member.id"
          class="flex items-center justify-between rounded-lg border border-gray-200 px-4 py-3"
        >
          <div class="flex items-center gap-3">
            <div class="flex h-8 w-8 items-center justify-center rounded-full bg-gray-100 text-xs font-medium text-gray-600">
              {{ member.user_email[0].toUpperCase() }}
            </div>
            <div>
              <p class="text-sm text-gray-900">{{ member.user_email }}</p>
              <p class="text-xs text-gray-400">ID: {{ member.user_id.slice(0, 8) }}…</p>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <UiBadge :variant="member.role === 'admin' ? 'primary' : 'default'" size="sm">
              {{ member.role }}
            </UiBadge>
            <UiSelect
              :modelValue="member.role"
              :options="roleOptions"
              class="w-28"
              @update:modelValue="(val) => handleRoleChange(member, String(val))"
            />
            <button
              @click="openRemoveDialog(member)"
              class="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors"
              title="Remove member"
            >
              <Trash2 class="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </template>

    <UiEmptyState
      v-else
      title="No teams found"
      description="You are not a member of any team."
      :icon="Users"
    />

    <!-- Add Member Dialog -->
    <UiDialog v-model:open="showAddDialog" title="Add Member" size="sm">
      <div class="space-y-4">
        <UiInput
          v-model="addForm.userId"
          label="User ID"
          placeholder="Paste the user's UUID"
          :error="addErrors.userId"
        />
        <UiSelect
          v-model="addForm.role"
          :options="roleOptions"
          label="Role"
        />
      </div>

      <template #footer>
        <UiButton variant="outline" @click="showAddDialog = false">Cancel</UiButton>
        <UiButton :loading="adding" @click="handleAddMember">Add Member</UiButton>
      </template>
    </UiDialog>

    <!-- Remove Confirmation Dialog -->
    <UiDialog v-model:open="showRemoveDialog" title="Remove Member" size="sm">
      <p class="text-sm text-gray-600">
        Remove <strong>{{ removingMember?.user_email }}</strong> from this team?
        This action cannot be undone.
      </p>

      <template #footer>
        <UiButton variant="outline" @click="showRemoveDialog = false">Cancel</UiButton>
        <UiButton variant="danger" :loading="removing" @click="confirmRemove">Remove</UiButton>
      </template>
    </UiDialog>
  </div>
</template>

<script setup lang="ts">
import { Users, UserPlus, Trash2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { Team, TeamMember } from '~/types/admin'
import { useAuthStore } from '~/stores/auth'

const api = useApi()
const authStore = useAuthStore()

const loadingTeams = ref(true)
const loadingMembers = ref(false)
const teams = ref<Team[]>([])
const selectedTeamId = ref<string>('')
const members = ref<TeamMember[]>([])

const showAddDialog = ref(false)
const addForm = ref({ userId: '', role: 'member' })
const addErrors = ref<{ userId?: string }>({})
const adding = ref(false)

const showRemoveDialog = ref(false)
const removingMember = ref<TeamMember | null>(null)
const removing = ref(false)

const teamOptions = computed(() =>
  teams.value.map(t => ({ label: t.name, value: t.id }))
)

const roleOptions = [
  { label: 'Member', value: 'member' },
  { label: 'Admin', value: 'admin' }
]

watch(selectedTeamId, async (id) => {
  if (id) await fetchMembers(id)
})

onMounted(async () => {
  await fetchTeams()
})

async function fetchTeams() {
  const orgId = authStore.user?.org_id
  if (!orgId) {
    loadingTeams.value = false
    return
  }

  try {
    loadingTeams.value = true
    teams.value = await api.orgs.getTeams(orgId) as Team[]
    if (teams.value.length > 0) {
      selectedTeamId.value = teams.value[0].id
      await fetchMembers(teams.value[0].id)
    }
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to load teams')
  } finally {
    loadingTeams.value = false
  }
}

async function fetchMembers(teamId: string) {
  try {
    loadingMembers.value = true
    members.value = await api.teams.getMembers(teamId) as TeamMember[]
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to load members')
  } finally {
    loadingMembers.value = false
  }
}

async function handleRoleChange(member: TeamMember, newRole: string) {
  if (newRole === member.role) return
  try {
    await api.teams.updateMemberRole(selectedTeamId.value, member.user_id, newRole)
    member.role = newRole
    toast.success('Role updated')
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to update role')
  }
}

async function handleAddMember() {
  addErrors.value = {}
  if (!addForm.value.userId.trim()) {
    addErrors.value.userId = 'User ID is required'
    return
  }

  try {
    adding.value = true
    await api.teams.addMember(selectedTeamId.value, addForm.value.userId.trim(), addForm.value.role)
    toast.success('Member added successfully')
    showAddDialog.value = false
    addForm.value = { userId: '', role: 'member' }
    await fetchMembers(selectedTeamId.value)
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to add member')
  } finally {
    adding.value = false
  }
}

function openRemoveDialog(member: TeamMember) {
  removingMember.value = member
  showRemoveDialog.value = true
}

async function confirmRemove() {
  if (!removingMember.value) return
  try {
    removing.value = true
    await api.teams.removeMember(selectedTeamId.value, removingMember.value.user_id)
    toast.success('Member removed')
    showRemoveDialog.value = false
    await fetchMembers(selectedTeamId.value)
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to remove member')
  } finally {
    removing.value = false
  }
}
</script>
