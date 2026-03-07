<template>
  <div class="mt-3">
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
            : 'border-gray-300 bg-white text-gray-700 hover:border-gray-500 hover:text-gray-900'
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
        class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-gray-500 focus:ring-1 focus:ring-gray-500"
      />
    </div>

    <div class="mt-3">
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
    // Single-select: replace selection
    if (selectedLabels.value.includes(label)) {
      selectedLabels.value = []
    } else {
      selectedLabels.value = [label]
    }
  } else {
    // Multi-select: toggle
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
</script>
