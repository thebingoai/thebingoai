<template>
  <div class="p-6">
    <div class="mb-6">
      <h2 class="text-2xl font-medium text-gray-900">Policies</h2>
    </div>

    <!-- Loading teams -->
    <div v-if="loadingTeams" class="space-y-4">
      <UiSkeleton class="h-10 w-64 rounded-lg" />
      <UiSkeleton class="h-48 w-full rounded-lg" />
    </div>

    <UiEmptyState
      v-else-if="teams.length === 0"
      title="No teams found"
      description="You are not a member of any team."
      :icon="Shield"
    />

    <template v-else>
      <!-- Team selector -->
      <div class="mb-6">
        <UiSelect
          v-if="teams.length > 1"
          v-model="selectedTeamId"
          :options="teamOptions"
          label="Select Team"
          class="w-64"
        />
        <div v-else class="flex items-center gap-2 mb-2">
          <Shield class="h-4 w-4 text-gray-400" />
          <span class="text-sm font-medium text-gray-900">{{ teams[0]?.name }}</span>
        </div>
      </div>

      <div v-if="loadingPolicies" class="space-y-4">
        <UiSkeleton class="h-64 w-full rounded-lg" />
        <UiSkeleton class="h-48 w-full rounded-lg" />
      </div>

      <template v-else>
        <!-- Tool Policies -->
        <UiCard class="p-5 mb-6">
          <div class="mb-4 flex items-center justify-between">
            <div>
              <h3 class="text-base font-medium text-gray-900">Tool Policies</h3>
              <p class="text-xs text-gray-500 mt-0.5">Control which tools this team can use</p>
            </div>
            <UiButton size="sm" :loading="savingTools" @click="saveToolPolicy">
              Save Changes
            </UiButton>
          </div>

          <div v-if="catalogByCategory.length === 0" class="text-sm text-gray-400">
            No tools in catalog.
          </div>

          <div v-else class="space-y-5">
            <div v-for="group in catalogByCategory" :key="group.category">
              <h4 class="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                {{ group.category }}
              </h4>
              <div class="space-y-2">
                <div
                  v-for="tool in group.tools"
                  :key="tool.tool_key"
                  class="flex items-center justify-between rounded-lg border border-gray-100 px-4 py-3"
                >
                  <div class="min-w-0 flex-1 pr-4">
                    <p class="text-sm font-medium text-gray-900">{{ tool.display_name }}</p>
                    <p v-if="tool.description" class="text-xs text-gray-500 mt-0.5 truncate">{{ tool.description }}</p>
                  </div>
                  <button
                    type="button"
                    @click="toggleTool(tool.tool_key)"
                    class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors"
                    :class="enabledTools.has(tool.tool_key) ? 'bg-blue-600' : 'bg-gray-200'"
                  >
                    <span
                      class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                      :class="enabledTools.has(tool.tool_key) ? 'translate-x-6' : 'translate-x-1'"
                    />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </UiCard>

        <!-- Connection Policies -->
        <UiCard class="p-5">
          <div class="mb-4 flex items-center justify-between">
            <div>
              <h3 class="text-base font-medium text-gray-900">Connection Policies</h3>
              <p class="text-xs text-gray-500 mt-0.5">Control which database connections this team can access</p>
            </div>
            <UiButton size="sm" :loading="savingConnections" @click="saveConnectionPolicy">
              Save Changes
            </UiButton>
          </div>

          <div v-if="connections.length === 0" class="text-sm text-gray-400">
            No database connections available.
          </div>

          <div v-else class="space-y-2">
            <div
              v-for="conn in connections"
              :key="conn.id"
              class="flex items-center justify-between rounded-lg border border-gray-100 px-4 py-3"
            >
              <div class="min-w-0 flex-1 pr-4">
                <p class="text-sm font-medium text-gray-900">{{ conn.name }}</p>
                <p class="text-xs text-gray-500">{{ conn.db_type }} · {{ conn.host }}</p>
              </div>
              <button
                type="button"
                @click="toggleConnection(conn.id)"
                class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors"
                :class="enabledConnections.has(conn.id) ? 'bg-blue-600' : 'bg-gray-200'"
              >
                <span
                  class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                  :class="enabledConnections.has(conn.id) ? 'translate-x-6' : 'translate-x-1'"
                />
              </button>
            </div>
          </div>
        </UiCard>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { Shield } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { Team, ToolCatalogItem, TeamToolPolicy, TeamConnectionPolicy } from '~/types/admin'
import type { DatabaseConnection } from '~/types/connection'
import { useAuthStore } from '~/stores/auth'

const api = useApi()
const authStore = useAuthStore()

const loadingTeams = ref(true)
const loadingPolicies = ref(false)
const teams = ref<Team[]>([])
const selectedTeamId = ref('')

const catalog = ref<ToolCatalogItem[]>([])
const enabledTools = ref(new Set<string>())
const savingTools = ref(false)

const connections = ref<DatabaseConnection[]>([])
const enabledConnections = ref(new Set<number>())
const savingConnections = ref(false)

const teamOptions = computed(() =>
  teams.value.map(t => ({ label: t.name, value: t.id }))
)

const catalogByCategory = computed(() => {
  const groups: Record<string, ToolCatalogItem[]> = {}
  for (const tool of catalog.value) {
    if (!groups[tool.category]) groups[tool.category] = []
    groups[tool.category].push(tool)
  }
  return Object.entries(groups).map(([category, tools]) => ({ category, tools }))
})

watch(selectedTeamId, async (id) => {
  if (id) await fetchPolicies(id)
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
      await fetchPolicies(teams.value[0].id)
    }
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to load teams')
  } finally {
    loadingTeams.value = false
  }
}

async function fetchPolicies(teamId: string) {
  try {
    loadingPolicies.value = true
    const [catalogData, toolPolicy, connPolicy, connsData] = await Promise.all([
      api.policies.getToolCatalog() as Promise<ToolCatalogItem[]>,
      api.policies.getToolPolicy(teamId) as Promise<TeamToolPolicy>,
      api.policies.getConnectionPolicy(teamId) as Promise<TeamConnectionPolicy>,
      api.connections.list() as Promise<DatabaseConnection[]>
    ])

    catalog.value = catalogData
    enabledTools.value = new Set(toolPolicy.tool_keys)
    connections.value = connsData
    enabledConnections.value = new Set(connPolicy.connection_ids)
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to load policies')
  } finally {
    loadingPolicies.value = false
  }
}

function toggleTool(toolKey: string) {
  if (enabledTools.value.has(toolKey)) {
    enabledTools.value.delete(toolKey)
  } else {
    enabledTools.value.add(toolKey)
  }
}

function toggleConnection(connId: number) {
  if (enabledConnections.value.has(connId)) {
    enabledConnections.value.delete(connId)
  } else {
    enabledConnections.value.add(connId)
  }
}

async function saveToolPolicy() {
  try {
    savingTools.value = true
    await api.policies.setToolPolicy(selectedTeamId.value, Array.from(enabledTools.value))
    toast.success('Tool policy saved')
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to save tool policy')
  } finally {
    savingTools.value = false
  }
}

async function saveConnectionPolicy() {
  try {
    savingConnections.value = true
    await api.policies.setConnectionPolicy(selectedTeamId.value, Array.from(enabledConnections.value))
    toast.success('Connection policy saved')
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to save connection policy')
  } finally {
    savingConnections.value = false
  }
}
</script>
