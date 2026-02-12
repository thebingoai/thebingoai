<template>
  <div>
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
    <Toaster position="top-right" :theme="colorMode.value as 'light' | 'dark'" />
  </div>
</template>

<script setup lang="ts">
const colorMode = useColorMode()

// Initialize keyboard shortcuts
useKeyboardShortcuts()
</script>
