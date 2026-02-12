import type { NamespaceInfo } from '~/types'

export const useNamespaces = () => {
  const { data: status } = useStatus()

  const namespaces = computed<NamespaceInfo[]>(() => {
    if (!status.value?.index?.namespaces) return []

    return Object.entries(status.value.index.namespaces).map(([name, data]) => ({
      name,
      vector_count: data.vector_count
    }))
  })

  const namespaceNames = computed(() => namespaces.value.map(ns => ns.name))

  return {
    namespaces,
    namespaceNames
  }
}
