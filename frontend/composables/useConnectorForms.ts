import { reactive } from 'vue'
import type { Component } from 'vue'

export interface ConnectorCapabilities {
  refresh?: { enabled: boolean; label?: string }  // default label "Refresh Schema"
  reprofile?: { enabled: boolean }
}

export interface ConnectorFormEntry {
  dbType: string
  createForm?: Component
  editForm?: Component      // replaces left-column edit body for this db_type
  editPanel?: Component     // replaces right-column panel content for this db_type
  capabilities?: ConnectorCapabilities
}

const registry = reactive(new Map<string, ConnectorFormEntry>())

export interface ConnectorFormRegistry {
  register: (entry: ConnectorFormEntry) => void
  get: (dbType: string) => ConnectorFormEntry | undefined
  hasCreate: (dbType: string) => boolean
  hasEditForm: (dbType: string) => boolean
  hasEditPanel: (dbType: string) => boolean
}

const api: ConnectorFormRegistry = {
  register(entry) {
    registry.set(entry.dbType, { ...registry.get(entry.dbType), ...entry })
  },
  get(dbType) {
    return registry.get(dbType)
  },
  hasCreate(dbType) {
    return !!registry.get(dbType)?.createForm
  },
  hasEditForm(dbType) {
    return !!registry.get(dbType)?.editForm
  },
  hasEditPanel(dbType) {
    return !!registry.get(dbType)?.editPanel
  },
}

export const useConnectorForms = (): ConnectorFormRegistry => api
