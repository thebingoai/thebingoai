<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useLineage, type LineageNode } from '~/composables/useLineage'

const props = defineProps<{
  scope?: string
}>()

const { graph, loading, error, fetchGraph } = useLineage()

const selected = ref<LineageNode | null>(null)
const filter = ref('')

const filteredGraph = computed(() => {
  const g = graph.value
  if (!g || !filter.value.trim()) return g
  const needle = filter.value.toLowerCase()
  const keep = new Set(g.nodes.filter(n => n.name.toLowerCase().includes(needle)).map(n => n.id))
  for (const e of g.edges) {
    if (keep.has(e.src)) keep.add(e.dst)
    if (keep.has(e.dst)) keep.add(e.src)
  }
  return {
    ...g,
    nodes: g.nodes.filter(n => keep.has(n.id)),
    edges: g.edges.filter(e => keep.has(e.src) && keep.has(e.dst)),
  }
})

const incompleteCount = computed(() => graph.value?.incomplete_widgets?.length ?? 0)

onMounted(async () => {
  const [kind, id] = String(props.scope ?? '').split('/')
  if (kind && id) {
    await fetchGraph(kind, id)
  } else {
    await fetchGraph()
  }
})

function onSelect(node: LineageNode) {
  selected.value = node
}

function onClose() {
  selected.value = null
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Toolbar -->
    <div class="px-4 py-3 border-b border-gray-200 dark:border-neutral-800 flex items-center gap-3">
      <h1 class="text-base font-medium text-gray-900 dark:text-neutral-100">Lineage</h1>
      <div class="flex-1 max-w-sm">
        <input
          v-model="filter"
          type="text"
          placeholder="Filter by name…"
          class="w-full text-sm px-3 py-1.5 rounded-md border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-gray-900 dark:text-neutral-100"
        />
      </div>
      <div v-if="incompleteCount > 0" class="text-xs px-2 py-1 rounded bg-yellow-100 text-yellow-800 border border-yellow-300">
        {{ incompleteCount }} widget(s) with incomplete lineage
      </div>
    </div>

    <div class="flex flex-1 min-h-0">
      <!-- Graph -->
      <div class="flex-1 relative">
        <div v-if="loading" class="absolute inset-0 flex items-center justify-center text-sm text-gray-500">
          Loading lineage…
        </div>
        <div v-else-if="error" class="absolute inset-0 flex items-center justify-center text-sm text-red-600">
          {{ error }}
        </div>
        <div v-else-if="!graph || graph.nodes.length === 0" class="absolute inset-0 flex items-center justify-center text-sm text-gray-500">
          No lineage data for this scope yet. Run a Pipeline or dbt model to populate the graph.
        </div>
        <LineageLineageGraph
          v-else
          :graph="filteredGraph"
          @select="onSelect"
        />
      </div>

      <!-- Detail panel -->
      <LineageNodeDetailPanel :node="selected" @close="onClose" />
    </div>
  </div>
</template>
