<template>
  <aside
    class="flex flex-col border-l border-gray-100 bg-white transition-all duration-200 overflow-hidden"
    :class="user ? 'w-72' : 'w-0'"
  >
    <template v-if="user">
      <!-- Header -->
      <div class="px-5 pt-5 pb-4 border-b border-gray-100">
        <div class="flex items-center justify-between mb-1">
          <div class="flex h-8 w-8 items-center justify-center rounded-full bg-gray-900 text-white text-sm font-light flex-shrink-0">
            {{ user.email.charAt(0).toUpperCase() }}
          </div>
          <button class="text-gray-400 hover:text-gray-600" @click="$emit('close')">
            <X class="h-4 w-4" />
          </button>
        </div>
        <p class="text-sm font-medium text-gray-900 truncate mt-2">{{ user.email }}</p>
        <p class="text-xs text-gray-400">
          Joined {{ user.created_at ? parseUtcDate(user.created_at).toLocaleDateString('en', { year: 'numeric', month: 'short', day: 'numeric' }) : 'unknown' }}
        </p>
      </div>

      <!-- Loading detail -->
      <div v-if="loadingDetail" class="flex-1 flex items-center justify-center">
        <div class="h-5 w-5 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin" />
      </div>

      <!-- Detail -->
      <div v-else class="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        <!-- Role -->
        <AdminRoleSelector
          :user-id="user.id"
          :role="detail?.role ?? user.role"
          :user-email="user.email"
          @updated="onRoleUpdated"
        />

        <!-- Credits -->
        <AdminCreditControl
          :user-id="user.id"
          :daily-limit="detail?.daily_limit ?? user.daily_limit"
          :used-today="detail?.used_today ?? user.used_today"
          @updated="onCreditUpdated"
        />

        <!-- Activity chart -->
        <AdminActivityChart :daily-totals="detail?.daily_totals ?? []" />

        <!-- Account status -->
        <div class="pt-2 border-t border-gray-100">
          <p class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Account</p>
          <button
            v-if="isActive"
            class="w-full text-sm text-red-500 border border-red-200 rounded-lg px-3 py-2 hover:bg-red-50 transition-colors"
            :disabled="actioning"
            @click="deactivate"
          >
            {{ actioning ? 'Working…' : 'Deactivate Account' }}
          </button>
          <button
            v-else
            class="w-full text-sm text-green-600 border border-green-200 rounded-lg px-3 py-2 hover:bg-green-50 transition-colors"
            :disabled="actioning"
            @click="activate"
          >
            {{ actioning ? 'Working…' : 'Activate Account' }}
          </button>
          <p v-if="actionError" class="mt-1 text-xs text-red-500">{{ actionError }}</p>
        </div>
      </div>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { X } from 'lucide-vue-next'
import { parseUtcDate } from '~/utils/format'
import type { AdminUser, AdminUserDetail } from '~/utils/api/adminApi'
import { toast } from 'vue-sonner'

const props = defineProps<{ user: AdminUser | null }>()
const emit = defineEmits<{ close: []; updated: [user: Partial<AdminUser>] }>()

const api = useApi()

const detail = ref<AdminUserDetail | null>(null)
const loadingDetail = ref(false)
const actioning = ref(false)
const actionError = ref('')

const isActive = computed(() =>
  detail.value ? detail.value.is_active : (props.user?.is_active ?? true)
)

watch(() => props.user, async (u) => {
  if (!u) { detail.value = null; return }
  loadingDetail.value = true
  detail.value = null
  try {
    detail.value = await api.admin.getUser(u.id)
  } finally {
    loadingDetail.value = false
  }
}, { immediate: true })

const onRoleUpdated = (role: string) => {
  if (detail.value) detail.value.role = role as 'admin' | 'user'
  emit('updated', { id: props.user!.id, role: role as 'admin' | 'user' })
}

const onCreditUpdated = (limit: number) => {
  if (detail.value) detail.value.daily_limit = limit
  emit('updated', { id: props.user!.id, daily_limit: limit })
}

const deactivate = async () => {
  actioning.value = true
  actionError.value = ''
  try {
    await api.admin.deactivateUser(props.user!.id)
    if (detail.value) detail.value.is_active = false
    emit('updated', { id: props.user!.id, is_active: false })
    toast.success('User deactivated')
  } catch (e: any) {
    actionError.value = e?.data?.detail || 'Failed to deactivate'
    toast.error('Failed to deactivate user')
  } finally {
    actioning.value = false
  }
}

const activate = async () => {
  actioning.value = true
  actionError.value = ''
  try {
    await api.admin.activateUser(props.user!.id)
    if (detail.value) detail.value.is_active = true
    emit('updated', { id: props.user!.id, is_active: true })
    toast.success('User activated')
  } catch (e: any) {
    actionError.value = e?.data?.detail || 'Failed to activate'
    toast.error('Failed to activate user')
  } finally {
    actioning.value = false
  }
}
</script>
