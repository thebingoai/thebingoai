import { defineStore } from 'pinia'

export const useLayoutStore = defineStore('layout', {
  state: () => ({
    isMainExpanded: false,      // mobile: whether sidebar is hidden
    sidebarCollapsed: false,    // desktop: icon-only collapsed sidebar
    sidebarWidth: 220,          // desktop: expanded sidebar width (px)
  }),

  actions: {
    toggleMainExpand() {
      this.isMainExpanded = !this.isMainExpanded
    },
    setMainExpanded(expanded: boolean) {
      this.isMainExpanded = expanded
    },
    toggleSidebarCollapsed() {
      this.sidebarCollapsed = !this.sidebarCollapsed
    },
    setSidebarWidth(w: number) {
      this.sidebarWidth = Math.min(Math.max(w, 160), 320)
    },
  }
})
