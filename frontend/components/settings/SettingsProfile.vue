<template>
  <div class="p-6">
    <h2 class="text-2xl font-medium text-gray-900 mb-6">Profile</h2>

    <UiCard class="p-6">
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-extralight text-gray-700 mb-1">Email</label>
          <div class="text-gray-900">{{ authStore.user?.email }}</div>
        </div>

        <div>
          <label class="block text-sm font-extralight text-gray-700 mb-1">Member Since</label>
          <div class="text-gray-900">{{ formatDate(authStore.user?.created_at) }}</div>
        </div>

        <div class="pt-4 border-t border-gray-200">
          <UiButton variant="danger" @click="handleLogout">
            Logout
          </UiButton>
        </div>
      </div>
    </UiCard>
  </div>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const router = useRouter()

const formatDate = (dateString?: string) => {
  if (!dateString) return 'Unknown'
  return new Date(dateString).toLocaleDateString()
}

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>
