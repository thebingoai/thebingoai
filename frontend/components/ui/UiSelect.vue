<template>
  <div class="w-full">
    <label v-if="label" :for="id" class="mb-1.5 block text-sm font-medium text-neutral-700 dark:text-neutral-300">
      {{ label }}
      <span v-if="required" class="text-error-500">*</span>
    </label>
    <Listbox :modelValue="modelValue" @update:modelValue="$emit('update:modelValue', $event)">
      <div class="relative">
        <ListboxButton :class="buttonClasses">
          <span class="block truncate text-left">{{ displayValue }}</span>
          <component :is="ChevronDown" class="h-5 w-5 text-neutral-400" />
        </ListboxButton>

        <Transition
          leave-active-class="transition duration-100 ease-in"
          leave-from-class="opacity-100"
          leave-to-class="opacity-0"
        >
          <ListboxOptions class="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-neutral-200 bg-white py-1 shadow-lg focus:outline-none dark:border-neutral-700 dark:bg-neutral-900">
            <ListboxOption
              v-for="option in options"
              :key="option.value"
              v-slot="{ active, selected }"
              :value="option.value"
              as="template"
            >
              <li
                :class="[
                  'relative cursor-pointer select-none px-3 py-2 text-sm',
                  active ? 'bg-brand-100 text-brand-900 dark:bg-brand-900/20 dark:text-brand-100' : 'text-neutral-900 dark:text-neutral-100'
                ]"
              >
                <span :class="['block truncate', selected ? 'font-semibold' : 'font-normal']">
                  {{ option.label }}
                </span>
                <component
                  v-if="selected"
                  :is="Check"
                  class="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-600 dark:text-brand-400"
                />
              </li>
            </ListboxOption>
          </ListboxOptions>
        </Transition>
      </div>
    </Listbox>
    <p v-if="error" class="mt-1.5 text-sm text-error-600 dark:text-error-400">
      {{ error }}
    </p>
    <p v-else-if="hint" class="mt-1.5 text-sm text-neutral-500 dark:text-neutral-400">
      {{ hint }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { Listbox, ListboxButton, ListboxOptions, ListboxOption } from '@headlessui/vue'
import { ChevronDown, Check } from 'lucide-vue-next'
import { cn } from '~/utils/cn'

export interface SelectOption {
  label: string
  value: string | number
}

interface Props {
  modelValue?: string | number
  options: SelectOption[]
  label?: string
  placeholder?: string
  error?: string
  hint?: string
  disabled?: boolean
  required?: boolean
  id?: string
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: 'Select an option',
  disabled: false,
  required: false
})

defineEmits<{
  'update:modelValue': [value: string | number]
}>()

const id = props.id || `select-${Math.random().toString(36).substr(2, 9)}`

const displayValue = computed(() => {
  const selected = props.options.find(opt => opt.value === props.modelValue)
  return selected?.label || props.placeholder
})

const baseClasses = 'relative w-full h-10 px-3 pr-10 rounded-lg border transition-colors focus-ring disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-between'
const stateClasses = computed(() => {
  if (props.error) return 'border-error-300 dark:border-error-700 bg-error-50 dark:bg-error-900/10'
  return 'border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100'
})

const buttonClasses = computed(() => cn(baseClasses, stateClasses.value))
</script>
