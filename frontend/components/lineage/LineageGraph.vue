<script setup lang="ts">
import { computed, watch, ref } from 'vue'
import { VueFlow, useVueFlow, type Node, type Edge } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import type { LineageGraph, LineageNode, LineageEdge } from '~/composables/useLineage'

const props = defineProps<{
  graph: LineageGraph | null
}>()

const emit = defineEmits<{
  (e: 'select', node: LineageNode): void
}>()

const NODE_W = 200
const NODE_H = 56
const COL_GAP = 80
const ROW_GAP = 24

const NODE_KIND_COLORS: Record<string, { bg: string; border: string }> = {
  connection: { bg: '#eff6ff', border: '#60a5fa' },
  table:      { bg: '#ecfdf5', border: '#34d399' },
  widget:     { bg: '#fef3c7', border: '#f59e0b' },
}

function layered(nodes: LineageNode[], edges: LineageEdge[]) {
  const adjOut: Record<string, string[]> = {}
  const inDeg: Record<string, number> = {}
  for (const n of nodes) { adjOut[n.id] = []; inDeg[n.id] = 0 }
  for (const e of edges) {
    if (!adjOut[e.src]) adjOut[e.src] = []
    if (inDeg[e.dst] === undefined) inDeg[e.dst] = 0
    adjOut[e.src].push(e.dst)
    inDeg[e.dst]++
  }
  // Layer = longest path from any root
  const layer: Record<string, number> = {}
  const queue: string[] = []
  for (const id of Object.keys(inDeg)) if (inDeg[id] === 0) { layer[id] = 0; queue.push(id) }
  const visited = new Set<string>(queue)
  while (queue.length) {
    const cur = queue.shift()!
    for (const nb of adjOut[cur] || []) {
      layer[nb] = Math.max(layer[nb] ?? 0, (layer[cur] ?? 0) + 1)
      if (!visited.has(nb)) { visited.add(nb); queue.push(nb) }
    }
  }
  const cols: Record<number, string[]> = {}
  for (const n of nodes) {
    const c = layer[n.id] ?? 0
    if (!cols[c]) cols[c] = []
    cols[c].push(n.id)
  }
  return cols
}

const flowNodes = computed<Node[]>(() => {
  const g = props.graph
  if (!g) return []
  const cols = layered(g.nodes, g.edges)
  const result: Node[] = []
  for (const colKey of Object.keys(cols)) {
    const x = parseInt(colKey, 10) * (NODE_W + COL_GAP)
    cols[+colKey].forEach((id, idx) => {
      const node = g.nodes.find(n => n.id === id)
      if (!node) return
      const colors = NODE_KIND_COLORS[node.kind] || { bg: '#f3f4f6', border: '#9ca3af' }
      result.push({
        id: node.id,
        type: 'default',
        position: { x, y: idx * (NODE_H + ROW_GAP) },
        data: { label: node.name, kind: node.kind, meta: node.meta, lineage: node },
        style: {
          background: colors.bg,
          border: `2px solid ${colors.border}`,
          borderRadius: '6px',
          padding: '8px 12px',
          width: `${NODE_W}px`,
          fontSize: '13px',
        },
      })
    })
  }
  return result
})

const flowEdges = computed<Edge[]>(() => {
  const g = props.graph
  if (!g) return []
  return g.edges.map((e, i) => ({
    id: `e${i}`,
    source: e.src,
    target: e.dst,
    animated: false,
    style: { stroke: '#9ca3af', strokeWidth: 1.5 },
    type: 'smoothstep',
  }))
})

function onNodeClick(_evt: any, node: Node) {
  emit('select', node.data?.lineage as LineageNode)
}
</script>

<template>
  <div class="lineage-graph w-full h-full">
    <VueFlow
      :nodes="flowNodes"
      :edges="flowEdges"
      :default-viewport="{ x: 0, y: 0, zoom: 0.85 }"
      fit-view-on-init
      @node-click="onNodeClick"
    />
  </div>
</template>

<style scoped>
.lineage-graph {
  min-height: 480px;
}
</style>
