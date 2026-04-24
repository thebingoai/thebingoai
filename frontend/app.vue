<template>
  <div>
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
