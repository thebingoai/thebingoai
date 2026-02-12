import { defineStore } from 'pinia'
import type { SearchHistoryItem } from '~/types'

export interface SearchState {
  // Current search
  query: string
  namespaces: string[]
  topK: number
  minScore: number
  dateRange: 'all' | '24h' | 'week' | 'month'

  // Search history
  history: SearchHistoryItem[]
}

export const useSearchStore = defineStore('search', {
  state: (): SearchState => ({
    query: '',
    namespaces: [],
    topK: 5,
    minScore: 0,
    dateRange: 'all',
    history: []
  }),

  actions: {
    setQuery(query: string) {
      this.query = query
    },

    setNamespaces(namespaces: string[]) {
      this.namespaces = namespaces
    },

    addNamespace(namespace: string) {
      if (!this.namespaces.includes(namespace)) {
        this.namespaces.push(namespace)
      }
    },

    removeNamespace(namespace: string) {
      this.namespaces = this.namespaces.filter(ns => ns !== namespace)
    },

    clearNamespaces() {
      this.namespaces = []
    },

    setTopK(topK: number) {
      this.topK = topK
    },

    setMinScore(score: number) {
      this.minScore = score
    },

    setDateRange(range: 'all' | '24h' | 'week' | 'month') {
      this.dateRange = range
    },

    addToHistory(item: SearchHistoryItem) {
      // Remove existing item with same query
      this.history = this.history.filter(h => h.query !== item.query)

      // Add to beginning
      this.history.unshift(item)

      // Keep only last 50 items
      if (this.history.length > 50) {
        this.history = this.history.slice(0, 50)
      }
    },

    clearHistory() {
      this.history = []
    },

    removeFromHistory(id: string) {
      this.history = this.history.filter(h => h.id !== id)
    },

    resetFilters() {
      this.namespaces = []
      this.topK = 5
      this.minScore = 0
      this.dateRange = 'all'
    }
  },

  persist: {
    paths: ['history']
  }
})
