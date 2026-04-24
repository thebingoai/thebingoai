import { reactive } from 'vue'
import type { Component } from 'vue'

export interface SettingsTab {
  id: string
  label: string
  component: Component
  condition?: () => boolean
  order?: number
}

const tabs = reactive<SettingsTab[]>([])

export interface SettingsTabRegistry {
  register: (tab: SettingsTab) => void
  list: () => SettingsTab[]
}

const registry: SettingsTabRegistry = {
  register(tab) {
    if (tabs.find(t => t.id === tab.id)) return
    tabs.push(tab)
  },
  list() {
    return [...tabs].sort((a, b) => (a.order ?? 100) - (b.order ?? 100))
  },
}

export const useSettingsTabs = (): SettingsTabRegistry => registry
