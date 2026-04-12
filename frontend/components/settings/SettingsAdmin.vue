<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between px-6 py-4 border-b border-gray-100">
      <div>
        <h1 class="text-lg font-medium text-gray-900">User Management</h1>
        <p class="text-xs text-gray-400 mt-0.5">Manage user roles, credits, and account status</p>
      </div>
    </div>
    <div class="flex flex-1 overflow-hidden min-h-0">
      <AdminUserTable
        ref="tableRef"
        :selected-id="selectedUser?.id"
        class="flex-1"
        @select="onSelectUser"
      />
      <AdminUserPanel
        :user="selectedUser"
        @close="selectedUser = null"
        @updated="onUserUpdated"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AdminUser } from '~/utils/api/adminApi'

const tableRef = ref<{ refresh: () => void } | null>(null)
const selectedUser = ref<AdminUser | null>(null)

const onSelectUser = (user: AdminUser) => {
  selectedUser.value = selectedUser.value?.id === user.id ? null : user
}

const onUserUpdated = (patch: Partial<AdminUser>) => {
  if (selectedUser.value && patch.id === selectedUser.value.id) {
    selectedUser.value = { ...selectedUser.value, ...patch }
  }
  tableRef.value?.refresh()
}
</script>
