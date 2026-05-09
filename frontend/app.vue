<template>
  <div class="relative min-h-screen overflow-hidden">
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
    <Toaster position="top-right" />
  </div>
</template>

<script setup lang="ts">
// Initialize keyboard shortcuts
useKeyboardShortcuts()
</script>
