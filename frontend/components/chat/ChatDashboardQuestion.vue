<template>
  <!-- Answered state: green card summary -->
  <div v-if="answered" class="mt-3 rounded-xl border border-green-200 dark:border-green-900/50 bg-green-50/50 dark:bg-green-950/30 p-3">
    <div class="mb-2 flex items-center gap-1.5">
      <span class="flex h-4.5 w-4.5 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/50">
        <svg class="h-3 w-3 text-green-600 dark:text-green-400" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
        </svg>
      </span>
      <span class="text-[10px] font-semibold uppercase tracking-wide text-green-700 dark:text-green-400">Answered</span>
    </div>
    <div class="flex flex-wrap gap-1.5">
      <span
        v-for="answer in parsedAnswers"
        :key="answer"
        class="inline-block rounded-md bg-green-100 dark:bg-green-900/40 px-2 py-0.5 text-sm font-medium text-green-800 dark:text-green-300"
      >
        {{ answer }}
      </span>
    </div>
  </div>

  <!-- Active state: indigo card with interactive options -->
  <div v-else class="mt-3 rounded-xl border border-indigo-200 bg-indigo-50/50 p-4">
    <!-- Header badge -->
    <div class="mb-3 flex items-center gap-1.5">
      <span class="flex h-4.5 w-4.5 items-center justify-center rounded-full bg-indigo-100">
        <svg class="h-3 w-3 text-indigo-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      </span>
      <span class="text-[10px] font-semibold uppercase tracking-wide text-indigo-700">Question</span>
    </div>

    <div class="flex flex-wrap gap-2">
      <button
        v-for="option in options"
        :key="option.label"
        @click="toggleOption(option.label)"
        :title="option.description"
        :class="[
          'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors',
          isSelected(option.label)
            ? 'border-gray-900 bg-gray-900 text-white'
            : 'border-indigo-200 bg-white text-gray-700 hover:border-indigo-400'
        ]"
      >
        <svg v-if="isSelected(option.label)" class="h-3.5 w-3.5 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
        </svg>
        {{ option.label }}
      </button>
    </div>

    <!-- "Other" text input (shown when "Other" is selected) -->
    <div v-if="otherSelected" class="mt-2">
      <input
        v-model="otherText"
        type="text"
        placeholder="Describe your requirement..."
        class="w-full rounded-lg border border-indigo-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400"
      />
    </div>

    <div class="mt-3 border-t border-indigo-100 pt-3">
      <UiButton
        size="sm"
        variant="primary"
        :disabled="selectedLabels.length === 0 || (otherSelected && !otherText.trim())"
        @click="confirm"
      >
        Confirm selection
      </UiButton>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Option {
  label: string
  description: string
}

const props = defineProps<{
  options: Option[]
  allowMultiple?: boolean
  answered?: boolean
  answeredText?: string
}>()

const emit = defineEmits<{
  submit: [text: string]
}>()

const selectedLabels = ref<string[]>([])
const otherText = ref('')

const otherSelected = computed(() => selectedLabels.value.includes('Other'))

const isSelected = (label: string) => selectedLabels.value.includes(label)

const toggleOption = (label: string) => {
  if (props.allowMultiple === false) {
    if (selectedLabels.value.includes(label)) {
      selectedLabels.value = []
    } else {
      selectedLabels.value = [label]
    }
  } else {
    const idx = selectedLabels.value.indexOf(label)
    if (idx === -1) {
      selectedLabels.value = [...selectedLabels.value, label]
    } else {
      selectedLabels.value = selectedLabels.value.filter(l => l !== label)
    }
  }
}

const confirm = () => {
  const parts = selectedLabels.value.map(label => {
    if (label === 'Other' && otherText.value.trim()) {
      return `Other: ${otherText.value.trim()}`
    }
    return label
  })
  emit('submit', parts.join(', '))
}

const parsedAnswers = computed(() => {
  if (!props.answeredText) return []
  return props.answeredText.split(', ').map(s => s.trim()).filter(Boolean)
})
</script>
