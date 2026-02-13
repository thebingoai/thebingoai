import { defineStore } from 'pinia'

export const useLayoutStore = defineStore('layout', {
  state: () => ({
    isMainExpanded: false
  }),

  actions: {
    toggleMainExpand() {
      this.isMainExpanded = !this.isMainExpanded
    },

    setMainExpanded(expanded: boolean) {
      this.isMainExpanded = expanded
    }
  }
})
