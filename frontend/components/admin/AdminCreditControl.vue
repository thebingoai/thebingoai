<template>
  <div class="space-y-2">
    <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">Daily Credit Limit</label>
    <div class="flex items-center gap-2">
      <input
        v-model.number="localLimit"
        type="number"
        min="0"
        class="w-24 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-gray-400 tabular-nums"
      />
      <button
        :disabled="saving || localLimit === props.dailyLimit"
        class="text-sm bg-gray-900 text-white rounded-lg px-3 py-2 hover:bg-gray-700 disabled:opacity-40 transition-colors"
        @click="save"
      >
        {{ saving ? 'Saving…' : 'Save' }}
      </button>
    </div>
    <!-- Progress bar -->
    <div class="space-y-1">
      <div class="flex justify-between text-xs text-gray-400">
        <span>{{ usedToday }} used today</span>
        <span>{{ Math.round(usedPercent) }}%</span>
      </div>
      <div class="h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div
          class="h-full rounded-full transition-all"
          :class="usedPercent >= 90 ? 'bg-red-400' : 'bg-orange-400'"
          :style="{ width: `${Math.min(usedPercent, 100)}%` }"
        />
      </div>
    </div>
    <p v-if="error" class="text-xs text-red-500">{{ error }}</p>
    <p v-if="success" class="text-xs text-green-600">Saved.</p>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  userId: string
  dailyLimit: number
  usedToday: number
}>()
const emit = defineEmits<{ updated: [limit: number] }>()

const api = useApi()
const localLimit = ref(props.dailyLimit)
const saving = ref(false)
const error = ref('')
const success = ref(false)

watch(() => props.dailyLimit, (v) => { localLimit.value = v })

const usedPercent = computed(() =>
  props.dailyLimit > 0 ? (props.usedToday / props.dailyLimit) * 100 : 0
)

const save = async () => {
  saving.value = true
  error.value = ''
  success.value = false
  try {
    await api.admin.setCredits(props.userId, localLimit.value)
    success.value = true
    emit('updated', localLimit.value)
    setTimeout(() => { success.value = false }, 2000)
  } catch (e: any) {
    error.value = e?.data?.detail || 'Failed to update'
  } finally {
    saving.value = false
  }
}
</script>
