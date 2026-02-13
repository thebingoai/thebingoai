<template>
  <div class="flex h-screen bg-white">
    <!-- Sidebar -->
    <AppSidebar />

    <!-- Main content -->
    <main class="flex flex-1 flex-col overflow-hidden">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
const authStore = useAuthStore()

// Load user on mount
onMounted(() => {
  if (process.client) {
    authStore.loadUser()
  }
})
</script>
