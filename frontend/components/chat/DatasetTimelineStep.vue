<template>
  <div class="flex gap-2.5">
    <!-- Left: icon + connector line -->
    <div class="flex flex-col items-center">
      <!-- Step icon -->
      <div
        class="w-3.5 h-3.5 rounded-full flex items-center justify-center shrink-0 z-[1]"
        :class="iconClasses"
      >
        <!-- Completed: checkmark -->
        <svg v-if="status === 'completed'" class="w-2 h-2" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <!-- Active: pulsing dot -->
        <div v-else-if="status === 'active'" class="w-1.5 h-1.5 rounded-full animate-pulse" :class="activeDotClass" />
        <!-- Failed: X -->
        <svg v-else-if="status === 'failed'" class="w-2 h-2" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
        <!-- Pending: empty -->
      </div>
      <!-- Connector line -->
      <div
        v-if="!isLast"
        class="w-px h-4"
        :class="connectorClasses"
      />
    </div>

    <!-- Right: label + timestamp -->
    <div class="flex-1 min-w-0 pt-px">
      <div class="flex items-center gap-1.5">
        <span class="text-[10px] font-medium" :class="labelColor">
          {{ status === 'active' ? activeLabel : (status === 'failed' ? failedLabel : label) }}
        </span>
        <span v-if="formattedTime" class="text-[9px] text-gray-300 ml-auto shrink-0">
          {{ formattedTime }}
        </span>
      </div>
      <!-- Error message -->
      <p v-if="error && status === 'failed'" class="text-[9px] text-red-400 mt-0.5">
        {{ error }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
type StepState = 'completed' | 'active' | 'pending' | 'failed'

const props = defineProps<{
  status: StepState
  label: string
  activeLabel: string
  timestamp: string | null
  isLast: boolean
  nextStatus?: StepState
  error?: string | null
}>()

const failedLabel = computed(() => props.label.replace(/built|profiled/i, 'failed').replace(/^Uploaded$/, 'Upload failed'))

const iconClasses = computed(() => {
  switch (props.status) {
    case 'completed': return 'bg-emerald-500'
    case 'active': return 'border-2 border-amber-400'
    case 'failed': return 'bg-red-500'
    default: return 'border-2 border-gray-200'
  }
})

const activeDotClass = computed(() => {
  // Use blue for uploading (first step), amber for the rest
  return props.label === 'Uploaded' ? 'bg-blue-500' : 'bg-amber-400'
})

const labelColor = computed(() => {
  switch (props.status) {
    case 'completed': return 'text-emerald-500'
    case 'active': return props.label === 'Uploaded' ? 'text-blue-500' : 'text-amber-500'
    case 'failed': return 'text-red-500'
    default: return 'text-gray-300'
  }
})

const connectorClasses = computed(() => {
  if (props.status === 'completed' && props.nextStatus === 'completed') {
    return 'bg-emerald-500'
  }
  if (props.status === 'completed' && props.nextStatus === 'active') {
    return 'bg-gradient-to-b from-emerald-500 to-gray-200'
  }
  if (props.status === 'completed' && props.nextStatus === 'failed') {
    return 'bg-gradient-to-b from-emerald-500 to-red-500'
  }
  return 'bg-gray-200'
})

const formattedTime = computed(() => {
  if (!props.timestamp) return null
  try {
    const date = new Date(props.timestamp)
    return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return null
  }
})
</script>
