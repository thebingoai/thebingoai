<template>
  <!-- Answered state: green card summary -->
  <div v-if="answered" class="mt-3 rounded-xl border border-green-200 bg-green-50/50 p-3 dark:border-green-800/50 dark:bg-green-950/30">
    <div class="mb-2 flex items-center gap-1.5">
      <span class="flex h-4.5 w-4.5 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/50">
        <svg class="h-3 w-3 text-green-600 dark:text-green-400" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
        </svg>
      </span>
      <span class="text-[10px] font-semibold uppercase tracking-wide text-green-700 dark:text-green-400">Answered</span>
    </div>
    <div class="space-y-1">
      <div
        v-for="(pair, idx) in parsedAnswers"
        :key="idx"
        class="flex gap-2 text-sm"
        :class="idx < parsedAnswers.length - 1 ? 'border-b border-green-100 pb-1.5 dark:border-green-800/30' : ''"
      >
        <span class="shrink-0 text-[11px] uppercase tracking-wide text-gray-500 min-w-[80px] pt-0.5 dark:text-neutral-400">{{ pair.label }}</span>
        <span class="font-medium text-gray-900 dark:text-neutral-100">{{ pair.value }}</span>
      </div>
    </div>
  </div>

  <!-- Active state: indigo card with interactive options -->
  <div v-else class="mt-3 rounded-xl border border-indigo-200 bg-indigo-50/50 p-4 dark:border-neutral-700 dark:bg-neutral-800/60">
    <!-- Header badge -->
    <div class="mb-3 flex items-center gap-1.5">
      <span class="flex h-4.5 w-4.5 items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-900/50">
        <svg class="h-3 w-3 text-indigo-600 dark:text-indigo-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      </span>
      <span class="text-[10px] font-semibold uppercase tracking-wide text-indigo-700 dark:text-indigo-400">Questions</span>
    </div>

    <!-- Question list with dividers -->
    <div class="divide-y divide-indigo-100 dark:divide-neutral-700">
      <div v-for="(q, qIdx) in questions" :key="qIdx" class="py-3 first:pt-0 last:pb-0">
        <!-- Header chip -->
        <div class="mb-1.5">
          <span
            v-if="q.header"
            class="inline-block rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-indigo-600 mr-2 dark:bg-indigo-900/50 dark:text-indigo-400"
          >
            {{ q.header }}
          </span>
          <span class="text-sm font-medium text-gray-900 dark:text-neutral-100">{{ q.question }}</span>
        </div>

        <!-- Vertical option rows (when options have descriptions) -->
        <div v-if="hasLongOptions(q)" class="space-y-1.5">
          <button
            v-for="option in q.options"
            :key="option.label"
            @click="toggleOption(qIdx, option.label)"
            :class="[
              'w-full text-left rounded-lg border px-3 py-2.5 transition-colors',
              isSelected(qIdx, option.label)
                ? 'border-gray-900 bg-gray-900 text-white dark:border-indigo-500 dark:bg-indigo-600'
                : 'border-indigo-200 bg-white text-gray-700 hover:border-indigo-400 dark:border-neutral-600 dark:bg-neutral-700 dark:text-neutral-200 dark:hover:border-indigo-400'
            ]"
          >
            <div class="flex items-center gap-2">
              <svg v-if="isSelected(qIdx, option.label)" class="h-3.5 w-3.5 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
              <span class="text-sm font-medium">{{ option.label }}</span>
            </div>
            <p
              v-if="option.description"
              :class="[
                'mt-0.5 text-xs',
                isSelected(qIdx, option.label) ? 'text-gray-300 dark:text-indigo-200' : 'text-gray-500 dark:text-neutral-400'
              ]"
            >
              {{ option.description }}
            </p>
          </button>

          <!-- Other option (vertical) -->
          <button
            @click="toggleOption(qIdx, 'Other')"
            :class="[
              'w-full text-left rounded-lg border px-3 py-2.5 transition-colors',
              isSelected(qIdx, 'Other')
                ? 'border-gray-900 bg-gray-900 text-white dark:border-indigo-500 dark:bg-indigo-600'
                : 'border-indigo-200 bg-white text-gray-700 hover:border-indigo-400 dark:border-neutral-600 dark:bg-neutral-700 dark:text-neutral-200 dark:hover:border-indigo-400'
            ]"
          >
            <div class="flex items-center gap-2">
              <svg v-if="isSelected(qIdx, 'Other')" class="h-3.5 w-3.5 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
              <span class="text-sm font-medium">Other</span>
            </div>
          </button>
        </div>

        <!-- Horizontal chips (when options are short / no descriptions) -->
        <div v-else class="flex flex-wrap gap-2">
          <button
            v-for="option in q.options"
            :key="option.label"
            @click="toggleOption(qIdx, option.label)"
            :title="option.description"
            :class="[
              'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors',
              isSelected(qIdx, option.label)
                ? 'border-gray-900 bg-gray-900 text-white dark:border-indigo-500 dark:bg-indigo-600'
                : 'border-indigo-200 bg-white text-gray-700 hover:border-indigo-400 dark:border-neutral-600 dark:bg-neutral-700 dark:text-neutral-200 dark:hover:border-indigo-400'
            ]"
          >
            <svg v-if="isSelected(qIdx, option.label)" class="h-3.5 w-3.5 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
            {{ option.label }}
          </button>

          <!-- Implicit "Other" chip -->
          <button
            @click="toggleOption(qIdx, 'Other')"
            :class="[
              'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors',
              isSelected(qIdx, 'Other')
                ? 'border-gray-900 bg-gray-900 text-white dark:border-indigo-500 dark:bg-indigo-600'
                : 'border-indigo-200 bg-white text-gray-700 hover:border-indigo-400 dark:border-neutral-600 dark:bg-neutral-700 dark:text-neutral-200 dark:hover:border-indigo-400'
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
            class="w-full rounded-lg border border-indigo-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 dark:border-neutral-600 dark:bg-neutral-700 dark:text-neutral-100 dark:placeholder-neutral-400 dark:focus:border-indigo-400"
          />
        </div>
      </div>
    </div>

    <!-- Confirm button -->
    <div class="mt-3 border-t border-indigo-100 pt-3 dark:border-neutral-700">
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
  answered?: boolean
  answeredText?: string
}>()

const emit = defineEmits<{
  submit: [text: string]
}>()

const selections = ref<Record<number, string[]>>({})
const otherTexts = ref<Record<number, string>>({})

const hasLongOptions = (q: Question) => q.options.some(o => o.description?.trim())

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

const parsedAnswers = computed(() => {
  if (!props.answeredText) return []
  return props.answeredText.split('\n').map((line, idx) => {
    const colonIdx = line.indexOf(':')
    if (colonIdx === -1) return { label: 'Answer', value: line.trim() }
    return {
      label: props.questions[idx]?.header || line.slice(0, colonIdx).trim(),
      value: line.slice(colonIdx + 1).trim()
    }
  })
})
</script>
