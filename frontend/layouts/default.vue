<template>
  <div class="min-h-screen bg-neutral-50 dark:bg-neutral-950">
    <!-- Mobile nav -->
    <MobileNav />

    <!-- Desktop sidebar -->
    <AppSidebar class="hidden lg:block" />

    <!-- Main content area -->
    <div
      class="flex flex-col"
      :class="{
        'lg:pl-sidebar': !settings.sidebarCollapsed,
        'lg:pl-sidebar-collapsed': settings.sidebarCollapsed
      }"
    >
      <!-- Header -->
      <AppHeader />

      <!-- Page content -->
      <main class="flex-1 pt-header">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
const settings = useSettingsStore()
</script>
