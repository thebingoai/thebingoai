<template>
  <div class="space-y-1">
    <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">Role</label>
    <select
      v-model="localRole"
      :disabled="saving"
      class="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-gray-400"
      @change="handleChange"
    >
      <option value="user">User</option>
      <option value="admin">Admin</option>
    </select>
    <p v-if="error" class="text-xs text-red-500">{{ error }}</p>
  </div>

  <!-- Confirmation dialog -->
  <UiDialog v-model:open="showConfirm" title="Promote to Admin?" size="sm">
    <p class="text-sm text-gray-600">
      This will give <strong>{{ userEmail }}</strong> full admin access, including the ability to manage other users.
    </p>
    <template #footer>
      <button class="text-sm text-gray-500 hover:text-gray-700 px-3 py-1.5" @click="cancelChange">Cancel</button>
      <button
        class="text-sm bg-gray-900 text-white rounded-lg px-4 py-1.5 hover:bg-gray-700"
        @click="confirmChange"
      >
        Confirm
      </button>
    </template>
  </UiDialog>
</template>

<script setup lang="ts">
const props = defineProps<{
  userId: string
  role: 'admin' | 'user'
  userEmail: string
}>()
const emit = defineEmits<{ updated: [role: string] }>()

const api = useApi()
const localRole = ref(props.role)
const saving = ref(false)
const error = ref('')
const showConfirm = ref(false)
let pendingRole = ''

watch(() => props.role, (v) => { localRole.value = v })

const handleChange = () => {
  if (localRole.value === 'admin') {
    pendingRole = 'admin'
    showConfirm.value = true
    localRole.value = props.role  // revert until confirmed
  } else {
    applyChange('user')
  }
}

const cancelChange = () => {
  showConfirm.value = false
  pendingRole = ''
}

const confirmChange = () => {
  showConfirm.value = false
  applyChange('admin')
}

const applyChange = async (role: 'admin' | 'user') => {
  saving.value = true
  error.value = ''
  try {
    await api.admin.setRole(props.userId, role)
    localRole.value = role
    emit('updated', role)
  } catch (e: any) {
    error.value = e?.data?.detail || 'Failed to update role'
    localRole.value = props.role
  } finally {
    saving.value = false
  }
}
</script>
