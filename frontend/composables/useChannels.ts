import { reactive } from 'vue'
import type { Component } from 'vue'

export interface ChannelEntry {
  id: string
  label: string
  component: Component
  order?: number
}

const channels = reactive<ChannelEntry[]>([])

export interface ChannelRegistry {
  register: (entry: ChannelEntry) => void
  list: () => ChannelEntry[]
}

const registry: ChannelRegistry = {
  register(entry) {
    if (channels.find(c => c.id === entry.id)) return
    channels.push(entry)
  },
  list() {
    return [...channels].sort((a, b) => (a.order ?? 100) - (b.order ?? 100))
  },
}

export const useChannels = (): ChannelRegistry => registry
