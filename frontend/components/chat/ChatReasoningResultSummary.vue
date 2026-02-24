<template>
  <!-- SQL query result: compact table -->
  <div v-if="isQueryResult">
    <div class="text-xs text-gray-500 mb-1">
      {{ result.row_count }} row{{ result.row_count !== 1 ? 's' : '' }}
      <span v-if="result.execution_time_ms"> · {{ result.execution_time_ms.toFixed(0) }}ms</span>
    </div>
    <div v-if="result.columns?.length" class="overflow-x-auto rounded border border-gray-100">
      <table class="min-w-full text-xs">
        <thead>
          <tr class="bg-gray-50">
            <th
              v-for="col in result.columns"
              :key="col"
              class="px-2 py-1 text-left text-gray-500 font-normal whitespace-nowrap"
            >{{ col }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, i) in previewRows"
            :key="i"
            class="border-t border-gray-50"
          >
            <td
              v-for="(cell, j) in row"
              :key="j"
              class="px-2 py-1 text-gray-700 whitespace-nowrap max-w-24 truncate"
            >{{ cell }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="result.rows?.length > 5" class="px-2 py-1 text-xs text-gray-400">
        Showing 5 of {{ result.rows.length }} rows
      </p>
    </div>
  </div>

  <!-- Sub-agent result (data_agent / rag_agent): show message + SQL -->
  <div v-else-if="isAgentResult">
    <p v-if="result.message" class="text-xs text-gray-700 line-clamp-3">{{ result.message }}</p>
    <div v-if="result.sql_queries?.length" class="mt-1 rounded bg-gray-50 border border-gray-100 p-2">
      <pre class="text-xs text-gray-700 whitespace-pre-wrap break-all">{{ result.sql_queries[0] }}</pre>
    </div>
  </div>

  <!-- Table list result -->
  <div v-else-if="Array.isArray(result)">
    <p class="text-xs text-gray-600">{{ result.slice(0, 10).join(', ') }}{{ result.length > 10 ? ` +${result.length - 10} more` : '' }}</p>
  </div>

  <!-- Generic fallback -->
  <div v-else>
    <p class="text-xs text-gray-600 break-all font-mono line-clamp-4">{{ JSON.stringify(result) }}</p>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  result: any
  toolName?: string
}>()

const isQueryResult = computed(() =>
  props.result &&
  typeof props.result === 'object' &&
  'columns' in props.result &&
  'rows' in props.result
)

const isAgentResult = computed(() =>
  props.result &&
  typeof props.result === 'object' &&
  'message' in props.result &&
  ('sql_queries' in props.result || 'success' in props.result)
)

const previewRows = computed(() => {
  if (!isQueryResult.value) return []
  return (props.result.rows || []).slice(0, 5)
})
</script>
