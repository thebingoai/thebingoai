<template>
  <div class="p-6">
    <div class="mb-6 flex items-center justify-between">
      <h2 class="text-2xl font-medium text-gray-900">Connections</h2>
      <UiButton @click="openCreateDialog">
        Add Connection
      </UiButton>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="space-y-4">
      <UiSkeleton class="h-32" />
      <UiSkeleton class="h-32" />
      <UiSkeleton class="h-32" />
    </div>

    <!-- Empty State -->
    <UiEmptyState
      v-else-if="connections.length === 0"
      title="No connections yet"
      description="Connect to your databases to start querying with AI"
      :icon="Database"
    >
      <template #action>
        <UiButton @click="openCreateDialog">
          Add Your First Connection
        </UiButton>
      </template>
    </UiEmptyState>

    <!-- Connections List -->
    <div v-else class="space-y-4">
      <UiCard
        v-for="connection in connections"
        :key="connection.id"
        class="p-6"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="mb-2 flex items-center gap-3">
              <h3 class="text-lg font-normal text-gray-900">{{ connection.name }}</h3>
              <UiBadge
                :variant="connection.db_type === 'postgres' ? 'info' : 'warning'"
                size="sm"
              >
                {{ connection.db_type === 'postgres' ? 'PostgreSQL' : 'MySQL' }}
              </UiBadge>
              <UiBadge
                v-if="!connection.is_active"
                variant="error"
                size="lg"
              >
                Inactive
              </UiBadge>
            </div>
            <p class="text-sm text-gray-600">
              {{ connection.host }}:{{ connection.port }}/{{ connection.database }}
            </p>
            <p v-if="connection.schema_generated_at" class="mt-1 text-xs text-gray-500">
              Schema updated {{ formatRelativeDate(connection.schema_generated_at) }}
            </p>
          </div>

          <div class="flex items-center gap-2">
            <UiButton
              variant="outline"
              size="sm"
              :loading="testingId === connection.id"
              @click="testConnection(connection.id)"
            >
              Test
            </UiButton>
            <UiDropdown
              :items="getDropdownItems(connection)"
              align="right"
            >
              <template #trigger>
                <UiButton variant="ghost" size="sm">
                  <component :is="MoreVertical" class="h-4 w-4" />
                </UiButton>
              </template>
            </UiDropdown>
          </div>
        </div>
      </UiCard>
    </div>

    <!-- Type Picker Bottom Sheet -->
    <UiBottomSheet
      v-model:open="showTypePicker"
      title="Choose a Database"
    >
      <div class="grid grid-cols-5 gap-3">
        <!-- PostgreSQL -->
        <button
          @click="selectConnectorType('postgres')"
          class="flex flex-col items-center justify-center gap-1 aspect-square rounded-lg border-2 border-gray-200 p-2 hover:border-blue-500 hover:bg-blue-50 transition-all"
        >
          <svg class="h-20 w-20" viewBox="0 0 432.071 445.383" xmlns="http://www.w3.org/2000/svg">
            <g fill="#336791">
              <path d="M323.205 324.227c2.833-23.601 1.984-27.062 19.563-23.239l4.463.392c13.517.615 31.199-2.174 41.587-7 22.362-10.376 35.622-27.7 13.572-23.148-50.297 10.376-53.755-6.655-53.755-6.655 53.111-78.803 75.313-178.836 56.149-203.322C352.514-5.534 262.036 26.049 260.522 26.869l-.482.089c-9.938-2.062-21.06-3.294-33.554-3.496-22.761-.374-40.032 5.967-53.133 15.904 0 0-161.408-66.498-153.899 83.628 1.597 31.936 45.777 241.655 98.47 178.31 19.259-23.163 37.871-42.748 37.871-42.748 9.242 6.14 20.307 9.272 31.912 8.147l.897-.765c-.281 2.876-.157 5.689.359 9.019-13.572 15.167-9.584 17.83-36.723 23.416-27.457 5.659-11.326 15.734-.797 18.367 12.768 3.193 42.305 7.716 62.268-20.224l-.795 3.188c5.325 4.26 4.965 30.619 5.72 49.452.756 18.834 1.05 36.196 3.86 45.739 2.808 9.54 8.315 33.577 36.2 26.732 23.413-5.736 35.94-20.08 37.448-44.38 1.183-19.093 3.585-25.045 3.507-48.974l2.525-1.812c.029 18.28 2.146 33.381 3.854 47.105 1.707 13.725 9.166 26.379 26.988 33.04 25.011 9.362 40.544-4.25 43.141-13.351 2.598-9.101 4.725-25.13 2.017-41.794-2.708-16.665-2.976-27.017-2.976-27.017s5.029-6.461 4.382-30.619c-.647-24.158-1.183-38.447 7.525-50.175l-.256.021z"/>
            </g>
          </svg>
          <div class="text-center">
            <h3 class="text-xs font-normal text-gray-900">PostgreSQL</h3>
            <p class="text-xs text-gray-600">Open-source relational database</p>
          </div>
        </button>

        <!-- MySQL -->
        <button
          @click="selectConnectorType('mysql')"
          class="flex flex-col items-center justify-center gap-1 aspect-square rounded-lg border-2 border-gray-200 p-2 hover:border-orange-500 hover:bg-orange-50 transition-all"
        >
          <svg class="h-20 w-20" viewBox="0 0 256 252" xmlns="http://www.w3.org/2000/svg">
            <path fill="#00546B" d="M235.648 194.212c-13.918-.347-24.705 1.045-33.752 4.872-2.61 1.043-6.786 1.044-7.134 4.35 1.392 1.392 1.566 3.654 2.784 5.567 2.09 3.479 5.741 8.177 9.047 10.614 3.653 2.783 7.308 5.566 11.134 8.002 6.786 4.176 14.442 6.611 21.053 10.787 3.829 2.434 7.654 5.568 11.482 8.177 1.914 1.39 3.131 3.654 5.568 4.523v-.521c-1.219-1.567-1.567-3.828-2.784-5.568-1.738-1.74-3.48-3.306-5.221-5.046-5.048-6.784-11.308-12.7-18.093-17.571-5.396-3.83-17.75-9.047-20.008-15.485 0 0-.175-.173-.348-.347 3.827-.348 8.35-1.566 12.005-2.436 5.912-1.565 11.308-1.217 17.398-2.784 2.783-.696 5.567-1.566 8.35-2.436v-1.565c-3.13-3.132-5.392-7.307-8.698-10.265-8.873-7.657-18.617-15.137-28.837-21.055-5.394-3.132-12.005-5.048-17.75-7.654-2.09-.696-5.567-1.566-6.784-3.306-3.133-3.827-4.698-8.699-7.135-13.047-5.04-9.568-9.866-20.184-14.576-30.23-3.13-6.786-5.044-13.572-8.872-19.834-17.92-29.577-37.406-47.497-67.33-65.07-6.438-3.653-14.093-5.219-22.27-7.132-4.348-.175-8.699-.522-13.046-.697-2.784-1.218-5.568-4.523-8.004-6.089C34.006 4.573 8.429-8.996 1.122 8.924c-4.698 11.308 6.96 22.441 10.96 28.143 2.96 4.001 6.786 8.524 8.874 13.046 1.392 3.132 1.566 6.263 2.958 9.569 2.784 7.654 5.221 16.178 8.872 23.311 1.914 3.653 4.001 7.48 6.437 10.786 1.392 2.088 3.827 2.957 4.348 5.915-2.435 3.48-2.61 8.7-4.003 13.049-6.263 19.66-3.826 44.017 5.046 58.457 2.784 4.348 9.395 13.572 18.268 10.091 7.83-3.132 6.09-13.046 8.35-21.75.522-2.09.176-3.48 1.219-4.872v.349c2.436 4.87 4.871 9.569 7.133 14.44 5.394 8.524 14.788 17.398 22.617 23.314 4.177 3.13 7.482 8.524 12.707 10.438v-.523h-.349c-1.044-1.566-2.61-2.261-4.001-3.48-3.131-3.13-6.612-6.958-9.047-10.438-7.306-9.744-13.745-20.357-19.486-31.665-2.784-5.392-5.22-11.308-7.481-16.701-1.045-2.088-1.045-5.22-2.784-6.263-2.61 3.827-6.437 7.133-8.351 11.83-3.304 7.481-3.653 16.702-4.871 26.27-.696.176-.349 0-.697.35-6.089-1.567-8.177-8.005-10.265-13.398-5.22-13.919-6.089-36.363-.175-52.19 1.565-4.176 8.702-17.398 5.915-21.23-1.391-3.654-6.263-5.742-8.872-8.525-2.959-3.477-6.088-7.829-8.004-11.83-4.697-10.264-6.96-21.75-11.833-32.015-2.262-4.871-6.263-9.744-9.57-14.093-3.653-4.872-7.829-8.351-10.788-14.268-1.043-2.088-2.436-5.046-1.218-7.133.173-1.74 1.044-2.611 2.784-3.131 2.784-1.218 10.613 1.044 13.398 2.09 7.482 2.434 13.572 4.871 19.834 8.699 2.958 1.913 6.088 5.568 9.742 6.612h4.35c6.787 1.566 14.267.522 20.707 2.09 11.485 2.958 21.75 7.654 31.665 12.7 30.23 15.66 54.762 37.929 71.68 66.506 2.436 4.175 3.48 8.003 5.566 12.354 4.175 8.7 9.396 17.574 13.572 26.097 4.348 8.872 8.699 17.75 14.093 25.402 2.959 4.001 14.787 6.09 20.008 8.177 3.827 1.567 9.918 3.132 13.572 5.046 6.787 3.48 13.398 7.481 19.834 11.308 3.305 1.914 13.572 6.09 14.268 10.265z"/>
          </svg>
          <div class="text-center">
            <h3 class="text-xs font-normal text-gray-900">MySQL</h3>
            <p class="text-xs text-gray-600">Popular open-source database</p>
          </div>
        </button>
      </div>
    </UiBottomSheet>

    <!-- Create/Edit Dialog -->
    <UiDialog
      v-model:open="showFormDialog"
      :title="getFormTitle()"
      size="lg"
    >
      <form @submit.prevent="handleFormSubmit" class="space-y-4">
        <UiInput
          v-model="form.name"
          label="Connection Name"
          placeholder="My Database"
          required
          :error="formErrors.name"
        />

        <div class="grid grid-cols-2 gap-4">
          <UiInput
            v-model="form.host"
            label="Host"
            placeholder="localhost"
            required
            :error="formErrors.host"
          />
          <UiInput
            v-model="form.port"
            label="Port"
            type="number"
            placeholder="5432"
            required
            :error="formErrors.port"
          />
        </div>

        <UiInput
          v-model="form.database"
          label="Database Name"
          placeholder="mydb"
          required
          :error="formErrors.database"
        />

        <div class="grid grid-cols-2 gap-4">
          <UiInput
            v-model="form.username"
            label="Username"
            placeholder="postgres"
            required
            :error="formErrors.username"
          />
          <UiInput
            v-model="form.password"
            label="Password"
            type="password"
            :placeholder="editingConnection ? 'Leave blank to keep current' : 'password'"
            :required="!editingConnection"
            :hint="editingConnection ? 'Leave blank to keep current password' : undefined"
            :error="formErrors.password"
          />
        </div>
      </form>

      <template #footer>
        <UiButton
          variant="outline"
          @click="showFormDialog = false"
        >
          Cancel
        </UiButton>
        <UiButton
          :loading="saving"
          @click="handleFormSubmit"
        >
          {{ editingConnection ? 'Save Changes' : 'Create Connection' }}
        </UiButton>
      </template>
    </UiDialog>

    <!-- Delete Confirmation Dialog -->
    <UiDialog
      v-model:open="showDeleteDialog"
      title="Delete Connection"
      size="sm"
    >
      <p class="text-sm text-gray-600">
        Are you sure you want to delete <strong>{{ deletingConnection?.name }}</strong>?
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
import { Database, MoreVertical, Edit, RefreshCw, Trash2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { DatabaseConnection, ConnectionFormData, DatabaseType } from '~/types/connection'
import type { DropdownItem } from '~/components/ui/UiDropdown.vue'

const api = useApi()

// State
const connections = ref<DatabaseConnection[]>([])
const loading = ref(true)
const showTypePicker = ref(false)
const showFormDialog = ref(false)
const editingConnection = ref<DatabaseConnection | null>(null)
const form = ref<ConnectionFormData>({
  name: '',
  db_type: 'postgres' as DatabaseType,
  host: '',
  port: 5432,
  database: '',
  username: '',
  password: ''
})
const formErrors = ref<Partial<Record<keyof ConnectionFormData, string>>>({})
const saving = ref(false)
const showDeleteDialog = ref(false)
const deletingConnection = ref<DatabaseConnection | null>(null)
const deleting = ref(false)
const testingId = ref<number | null>(null)
const refreshingId = ref<number | null>(null)

// Fetch connections on mount
onMounted(async () => {
  await fetchConnections()
})

// Actions
async function fetchConnections() {
  try {
    loading.value = true
    const response = await api.connections.list() as DatabaseConnection[]
    connections.value = response
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to fetch connections')
  } finally {
    loading.value = false
  }
}

function selectConnectorType(type: DatabaseType) {
  form.value.db_type = type
  form.value.port = type === 'postgres' ? 5432 : 3306
  showTypePicker.value = false
  showFormDialog.value = true
}

function openCreateDialog() {
  editingConnection.value = null
  form.value = {
    name: '',
    db_type: 'postgres',
    host: '',
    port: 5432,
    database: '',
    username: '',
    password: ''
  }
  formErrors.value = {}
  showTypePicker.value = true
}

function getFormTitle(): string {
  if (editingConnection.value) {
    return 'Edit Connection'
  }
  const dbName = form.value.db_type === 'postgres' ? 'PostgreSQL' : 'MySQL'
  return `New ${dbName} Connection`
}

function openEditDialog(connection: DatabaseConnection) {
  editingConnection.value = connection
  form.value = {
    name: connection.name,
    db_type: connection.db_type,
    host: connection.host,
    port: connection.port,
    database: connection.database,
    username: connection.username,
    password: '' // Blank by default
  }
  formErrors.value = {}
  showFormDialog.value = true
}

function validateForm(): boolean {
  formErrors.value = {}
  let isValid = true

  if (!form.value.name.trim()) {
    formErrors.value.name = 'Connection name is required'
    isValid = false
  }

  if (!form.value.host.trim()) {
    formErrors.value.host = 'Host is required'
    isValid = false
  }

  if (!form.value.port || form.value.port < 1 || form.value.port > 65535) {
    formErrors.value.port = 'Valid port is required (1-65535)'
    isValid = false
  }

  if (!form.value.database.trim()) {
    formErrors.value.database = 'Database name is required'
    isValid = false
  }

  if (!form.value.username.trim()) {
    formErrors.value.username = 'Username is required'
    isValid = false
  }

  if (!editingConnection.value && !form.value.password) {
    formErrors.value.password = 'Password is required'
    isValid = false
  }

  return isValid
}

async function handleFormSubmit() {
  if (!validateForm()) return

  try {
    saving.value = true

    // Build payload
    const payload: any = {
      name: form.value.name,
      db_type: form.value.db_type,
      host: form.value.host,
      port: Number(form.value.port),
      database: form.value.database,
      username: form.value.username
    }

    // Only include password if it's provided (for edits, empty password = keep current)
    if (form.value.password) {
      payload.password = form.value.password
    }

    if (editingConnection.value) {
      await api.connections.update(String(editingConnection.value.id), payload)
      toast.success('Connection updated successfully')
    } else {
      await api.connections.create(payload)
      toast.success('Connection created successfully')
    }

    showFormDialog.value = false
    await fetchConnections()
  } catch (err: any) {
    const errorMessage = err?.data?.detail || err?.message || 'Failed to save connection'
    toast.error(errorMessage)
  } finally {
    saving.value = false
  }
}

async function testConnection(id: number) {
  try {
    testingId.value = id
    const response = await api.connections.test(String(id)) as { success: boolean; message: string }

    if (response.success) {
      toast.success(response.message || 'Connection test successful')
    } else {
      toast.error(response.message || 'Connection test failed')
    }
  } catch (err: any) {
    const errorMessage = err?.data?.detail || err?.message || 'Connection test failed'
    toast.error(errorMessage)
  } finally {
    testingId.value = null
  }
}

async function refreshSchema(connection: DatabaseConnection) {
  try {
    refreshingId.value = connection.id
    await api.connections.refreshSchema(String(connection.id))
    toast.success('Schema refreshed successfully')
    await fetchConnections()
  } catch (err: any) {
    const errorMessage = err?.data?.detail || err?.message || 'Failed to refresh schema'
    toast.error(errorMessage)
  } finally {
    refreshingId.value = null
  }
}

function openDeleteDialog(connection: DatabaseConnection) {
  deletingConnection.value = connection
  showDeleteDialog.value = true
}

async function confirmDelete() {
  if (!deletingConnection.value) return

  try {
    deleting.value = true
    await api.connections.delete(String(deletingConnection.value.id))
    toast.success('Connection deleted successfully')
    showDeleteDialog.value = false
    await fetchConnections()
  } catch (err: any) {
    const errorMessage = err?.data?.detail || err?.message || 'Failed to delete connection'
    toast.error(errorMessage)
  } finally {
    deleting.value = false
  }
}

function getDropdownItems(connection: DatabaseConnection): DropdownItem[] {
  return [
    {
      label: 'Edit',
      icon: Edit,
      onClick: () => openEditDialog(connection)
    },
    {
      label: 'Refresh Schema',
      icon: RefreshCw,
      onClick: () => refreshSchema(connection)
    },
    {
      label: 'Delete',
      icon: Trash2,
      onClick: () => openDeleteDialog(connection),
      danger: true
    }
  ]
}

function formatRelativeDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 30) return `${diffDays}d ago`

  return date.toLocaleDateString()
}
</script>
