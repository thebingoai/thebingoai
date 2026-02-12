import { defineStore } from 'pinia'
import type {
  LLMProvider,
  ConnectionStatus,
  LayoutDensity,
  FontSize
} from '~/types'

export interface SettingsState {
  // Backend connection
  backendUrl: string
  connectionStatus: ConnectionStatus

  // Defaults
  defaultNamespace: string
  defaultProvider: LLMProvider
  defaultModel: string

  // Appearance (theme is handled by @nuxtjs/color-mode)
  density: LayoutDensity
  fontSize: FontSize
  animationsEnabled: boolean

  // Layout
  sidebarCollapsed: boolean
}

export const useSettingsStore = defineStore('settings', {
  state: (): SettingsState => ({
    // Backend connection
    backendUrl: 'http://localhost:8000',
    connectionStatus: 'disconnected',

    // Defaults
    defaultNamespace: 'default',
    defaultProvider: 'openai',
    defaultModel: 'gpt-4',

    // Appearance
    density: 'comfortable',
    fontSize: 'medium',
    animationsEnabled: true,

    // Layout
    sidebarCollapsed: false
  }),

  actions: {
    setBackendUrl(url: string) {
      this.backendUrl = url.replace(/\/$/, '') // Remove trailing slash
    },

    setConnectionStatus(status: ConnectionStatus) {
      this.connectionStatus = status
    },

    setDefaultNamespace(namespace: string) {
      this.defaultNamespace = namespace
    },

    setDefaultProvider(provider: LLMProvider) {
      this.defaultProvider = provider
    },

    setDefaultModel(model: string) {
      this.defaultModel = model
    },

    setDensity(density: LayoutDensity) {
      this.density = density
    },

    setFontSize(size: FontSize) {
      this.fontSize = size
    },

    setAnimationsEnabled(enabled: boolean) {
      this.animationsEnabled = enabled
    },

    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
    },

    setSidebarCollapsed(collapsed: boolean) {
      this.sidebarCollapsed = collapsed
    }
  },

  persist: true
})
