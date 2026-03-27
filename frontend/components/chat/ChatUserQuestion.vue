<template>
  <div class="mt-3 space-y-4">
    <div v-for="(q, qIdx) in questions" :key="qIdx">
      <!-- Question header chip + question text -->
      <div class="mb-2">
        <span
          v-if="q.header"
          class="inline-block rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-gray-500 mr-2"
        >
          {{ q.header }}
        </span>
        <span class="text-sm font-medium text-gray-900">{{ q.question }}</span>
      </div>

      <!-- Option chips -->
      <div class="flex flex-wrap gap-2">
        <button
          v-for="option in q.options"
          :key="option.label"
          @click="toggleOption(qIdx, option.label)"
          :title="option.description"
          :class="[
            'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors',
            isSelected(qIdx, option.label)
              ? 'border-gray-900 bg-gray-900 text-white'
              : 'border-gray-300 bg-white text-gray-700 hover:border-gray-500 hover:text-gray-900'
          ]"
        >
          <svg v-if="isSelected(qIdx, option.label)" class="h-3.5 w-3.5 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
          </svg>
          {{ option.label }}
        </button>

        <!-- Implicit "Other" option -->
        <button
          @click="toggleOption(qIdx, 'Other')"
          :class="[
            'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors',
            isSelected(qIdx, 'Other')
              ? 'border-gray-900 bg-gray-900 text-white'
              : 'border-gray-300 bg-white text-gray-700 hover:border-gray-500 hover:text-gray-900'
          ]"
        >
          <svg v-if="isSelected(qIdx, 'Other')" class="h-3.5 w-3.5 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
          </svg>
          Other
        </button>
      </div>

      <!-- "Other" text input -->
      <div v-if="isSelected(qIdx, 'Other')" class="mt-2">
        <input
          v-model="otherTexts[qIdx]"
          type="text"
          placeholder="Describe your preference..."
          class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-gray-500 focus:ring-1 focus:ring-gray-500"
        />
      </div>
    </div>

    <div class="mt-3">
      <UiButton
        size="sm"
        variant="primary"
        :disabled="!allAnswered"
        @click="confirm"
      >
        {{ questions.length > 1 ? 'Confirm selections' : 'Confirm selection' }}
      </UiButton>
    </div>
  </div>
</template>

<script setup lang="ts">
interface QuestionOption {
  label: string
  description: string
}

interface Question {
  question: string
  header?: string
  options: QuestionOption[]
  select?: 'single' | 'multi'
}

const props = defineProps<{
  questions: Question[]
}>()

const emit = defineEmits<{
  submit: [text: string]
}>()

const selections = ref<Record<number, string[]>>({})
const otherTexts = ref<Record<number, string>>({})

const isSelected = (qIdx: number, label: string) =>
  (selections.value[qIdx] || []).includes(label)

const toggleOption = (qIdx: number, label: string) => {
  const current = selections.value[qIdx] || []
  const isMulti = props.questions[qIdx]?.select === 'multi'

  if (!isMulti) {
    selections.value = {
      ...selections.value,
      [qIdx]: current.includes(label) ? [] : [label],
    }
  } else {
    const idx = current.indexOf(label)
    selections.value = {
      ...selections.value,
      [qIdx]: idx === -1
        ? [...current, label]
        : current.filter(l => l !== label),
    }
  }
}

const allAnswered = computed(() =>
  props.questions.every((_, i) => {
    const sel = selections.value[i] || []
    if (sel.length === 0) return false
    if (sel.includes('Other') && !(otherTexts.value[i] || '').trim()) return false
    return true
  })
)

const confirm = () => {
  const parts = props.questions.map((q, i) => {
    const sel = selections.value[i] || []
    const answers = sel.map(label => {
      if (label === 'Other') {
        const txt = (otherTexts.value[i] || '').trim()
        return txt ? `Other: ${txt}` : null
      }
      return label
    }).filter(Boolean)
    return `${q.question}: ${answers.join(', ')}`
  })
  emit('submit', parts.join('\n'))
}
</script>
