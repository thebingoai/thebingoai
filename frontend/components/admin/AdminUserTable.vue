<template>
  <div class="flex flex-col h-full">
    <!-- Toolbar -->
    <div class="flex items-center gap-3 px-6 py-4 border-b border-gray-100">
      <div class="relative flex-1 max-w-xs">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          v-model="search"
          type="text"
          placeholder="Search users..."
          class="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-gray-400"
          @input="onSearchInput"
        />
      </div>
      <select
        v-model="roleFilter"
        class="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-gray-400"
        @change="load"
      >
        <option value="">All Roles</option>
        <option value="admin">Admin</option>
        <option value="user">User</option>
      </select>
      <select
        v-model="statusFilter"
        class="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-gray-400"
        @change="load"
      >
        <option value="">All Status</option>
        <option value="active">Active</option>
        <option value="inactive">Inactive</option>
      </select>
    </div>

    <!-- Table -->
    <div class="flex-1 overflow-auto">
      <table class="w-full text-sm">
        <thead class="sticky top-0 bg-gray-50 border-b border-gray-100">
          <tr>
            <th class="text-left px-6 py-3 font-medium text-gray-500 text-xs uppercase tracking-wide">Email</th>
            <th class="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wide">Role</th>
            <th class="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wide">Credits</th>
            <th class="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wide">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="user in users"
            :key="user.id"
            class="border-b border-gray-50 cursor-pointer hover:bg-gray-50 transition-colors"
            :class="selectedId === user.id ? 'bg-indigo-50' : ''"
            @click="$emit('select', user)"
          >
            <td class="px-6 py-3 text-gray-900">{{ user.email }}</td>
            <td class="px-4 py-3">
              <span
                class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
                :class="user.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'"
              >
                {{ user.role }}
              </span>
            </td>
            <td class="px-4 py-3 text-gray-600 tabular-nums">
              {{ user.used_today }} / {{ user.daily_limit }}
            </td>
            <td class="px-4 py-3">
              <span class="flex items-center gap-1.5 text-xs">
                <span
                  class="h-1.5 w-1.5 rounded-full"
                  :class="user.is_active ? 'bg-green-500' : 'bg-red-400'"
                />
                {{ user.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
          </tr>
          <tr v-if="users.length === 0 && !loading">
            <td colspan="4" class="px-6 py-12 text-center text-sm text-gray-400">
              No users found.
            </td>
          </tr>
          <tr v-if="loading">
            <td colspan="4" class="px-6 py-12 text-center">
              <div class="h-4 w-4 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin mx-auto" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="total > perPage" class="flex items-center justify-between px-6 py-3 border-t border-gray-100 text-sm text-gray-500">
      <span>{{ total }} users</span>
      <div class="flex items-center gap-2">
        <button
          :disabled="page <= 1"
          class="px-2 py-1 rounded hover:bg-gray-100 disabled:opacity-40"
          @click="page--; load()"
        >
          &lsaquo;
        </button>
        <span>{{ page }} / {{ totalPages }}</span>
        <button
          :disabled="page >= totalPages"
          class="px-2 py-1 rounded hover:bg-gray-100 disabled:opacity-40"
          @click="page++; load()"
        >
          &rsaquo;
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Search } from 'lucide-vue-next'
import type { AdminUser } from '~/utils/api/adminApi'

const props = defineProps<{ selectedId?: string | null }>()
const emit = defineEmits<{ select: [user: AdminUser] }>()

const api = useApi()

const users = ref<AdminUser[]>([])
const total = ref(0)
const page = ref(1)
const perPage = 20
const search = ref('')
const roleFilter = ref('')
const statusFilter = ref('')
const loading = ref(false)

const totalPages = computed(() => Math.ceil(total.value / perPage))

let searchTimeout: ReturnType<typeof setTimeout>
const onSearchInput = () => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => { page.value = 1; load() }, 300)
}

const load = async () => {
  loading.value = true
  try {
    const result = await api.admin.getUsers({
      search: search.value || undefined,
      role: roleFilter.value || undefined,
      status: statusFilter.value || undefined,
      page: page.value,
      per_page: perPage,
    })
    users.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

const refresh = () => load()
defineExpose({ refresh })

onMounted(load)
</script>
