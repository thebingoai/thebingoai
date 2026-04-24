import { reactive } from 'vue'
import type { Component } from 'vue'

export interface ConnectorFormEntry {
  dbType: string
  createForm?: Component
  editPanel?: Component
}

const registry = reactive(new Map<string, ConnectorFormEntry>())

export interface ConnectorFormRegistry {
  register: (entry: ConnectorFormEntry) => void
  get: (dbType: string) => ConnectorFormEntry | undefined
  hasCreate: (dbType: string) => boolean
  hasEdit: (dbType: string) => boolean
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
  hasEdit(dbType) {
    return !!registry.get(dbType)?.editPanel
  },
}

export const useConnectorForms = (): ConnectorFormRegistry => api
