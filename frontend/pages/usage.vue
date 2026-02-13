<template>
  <div class="p-8">
    <h1 class="text-3xl font-bold mb-6">Usage Analytics</h1>

    <div class="mb-6">
      <select v-model="selectedDays" @change="loadData"
        class="px-4 py-2 border rounded-md">
        <option :value="7">Last 7 days</option>
        <option :value="30">Last 30 days</option>
        <option :value="90">Last 90 days</option>
      </select>
    </div>

    <div v-if="usage.loading.value" class="text-center py-8">Loading...</div>

    <div v-else-if="usage.summary.value" class="space-y-6">
      <div class="grid grid-cols-3 gap-4">
        <div class="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div class="text-sm text-blue-600 mb-1">Total Operations</div>
          <div class="text-2xl font-bold">{{ usage.summary.value.totals.operations.toLocaleString() }}</div>
        </div>
        <div class="p-4 bg-green-50 border border-green-200 rounded-lg">
          <div class="text-sm text-green-600 mb-1">Total Tokens</div>
          <div class="text-2xl font-bold">{{ usage.summary.value.totals.tokens.toLocaleString() }}</div>
        </div>
        <div class="p-4 bg-purple-50 border border-purple-200 rounded-lg">
          <div class="text-sm text-purple-600 mb-1">Total Cost</div>
          <div class="text-2xl font-bold">${{ usage.summary.value.totals.cost.toFixed(4) }}</div>
        </div>
      </div>

      <div>
        <h2 class="text-xl font-bold mb-4">By Operation</h2>
        <div class="space-y-2">
          <div v-for="(data, op) in usage.summary.value.by_operation" :key="op"
            class="p-3 border rounded-lg flex justify-between items-center">
            <div>
              <div class="font-semibold capitalize">{{ op.replace('_', ' ') }}</div>
              <div class="text-sm text-gray-600">{{ data.count }} operations</div>
            </div>
            <div class="text-right">
              <div>{{ data.tokens.toLocaleString() }} tokens</div>
              <div class="text-sm text-gray-600">${{ data.cost.toFixed(4) }}</div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="usage.dailyUsage.value.length > 0">
        <h2 class="text-xl font-bold mb-4">Daily Usage</h2>
        <div class="overflow-x-auto">
          <table class="min-w-full border">
            <thead class="bg-gray-50">
              <tr>
                <th class="border px-4 py-2 text-left">Date</th>
                <th class="border px-4 py-2 text-right">Operations</th>
                <th class="border px-4 py-2 text-right">Tokens</th>
                <th class="border px-4 py-2 text-right">Cost</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="day in usage.dailyUsage.value" :key="day.date">
                <td class="border px-4 py-2">{{ day.date }}</td>
                <td class="border px-4 py-2 text-right">{{ day.operations }}</td>
                <td class="border px-4 py-2 text-right">{{ day.tokens.toLocaleString() }}</td>
                <td class="border px-4 py-2 text-right">${{ day.cost.toFixed(4) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: 'auth'
})

const usage = useUsageNew()
const selectedDays = ref(30)

async function loadData() {
  await Promise.all([
    usage.loadSummary(selectedDays.value),
    usage.loadDailyUsage(selectedDays.value)
  ])
}

onMounted(() => {
  loadData()
})
</script>
