<template>
  <div class="flex h-screen bg-[var(--paper-0)] overflow-hidden">
    <!-- Mobile backdrop -->
    <div
      v-if="isMobile && !layoutStore.isMainExpanded"
      class="fixed inset-0 z-30 bg-black/30"
      @click="layoutStore.setMainExpanded(true)"
    />

    <!-- Sidebar (desktop: inline flex item; mobile: fixed overlay) -->
    <AppSidebar />

    <!-- Resize handle between sidebar and main (desktop only) -->
    <div
      v-if="!isMobile && !layoutStore.sidebarCollapsed"
      class="sidebar-resize-handle"
      @mousedown="startSidebarResize"
    />

    <!-- Main content — fills remaining space -->
    <main class="flex flex-1 flex-col overflow-hidden min-w-0">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
const layoutStore = useLayoutStore()
const chatStore = useChatStore()
const chat = useChat()
const route = useRoute()
const { isMobile } = useIsMobile()

// ── Sidebar resize ──────────────────────────────────────────
let resizeStartX = 0
let resizeStartW = 0

const startSidebarResize = (e: MouseEvent) => {
  resizeStartX = e.clientX
  resizeStartW = layoutStore.sidebarWidth
  document.addEventListener('mousemove', onSidebarResize)
  document.addEventListener('mouseup', stopSidebarResize)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

const onSidebarResize = (e: MouseEvent) => {
  layoutStore.setSidebarWidth(resizeStartW + (e.clientX - resizeStartX))
}

const stopSidebarResize = () => {
  document.removeEventListener('mousemove', onSidebarResize)
  document.removeEventListener('mouseup', stopSidebarResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

// ── Mobile sidebar auto-hide ────────────────────────────────
watch(isMobile, (mobile) => {
  if (mobile && !layoutStore.isMainExpanded) {
    layoutStore.setMainExpanded(true)
  }
}, { immediate: true })
</script>

<style scoped>
.sidebar-resize-handle {
  width: 4px;
  flex-shrink: 0;
  cursor: col-resize;
  background: transparent;
  transition: background 0.15s;
  position: relative;
  z-index: 10;
}
.sidebar-resize-handle::after {
  content: '';
  position: absolute;
  inset-y: 0;
  left: -2px;
  right: -2px;
}
.sidebar-resize-handle:hover {
  background: var(--ember);
}
</style>
