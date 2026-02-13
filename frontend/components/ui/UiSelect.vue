<template>
  <div class="w-full">
    <label v-if="label" :for="id" class="mb-1.5 block text-sm font-medium text-gray-700">
      {{ label }}
      <span v-if="required" class="text-red-600">*</span>
    </label>
    <Listbox :modelValue="modelValue" @update:modelValue="$emit('update:modelValue', $event)">
      <div class="relative">
        <ListboxButton :class="buttonClasses">
          <span class="block truncate text-left">{{ displayValue }}</span>
          <component :is="ChevronDown" class="h-5 w-5 text-gray-400" />
        </ListboxButton>

        <Transition
          leave-active-class="opacity-0"
          leave-from-class="opacity-100"
          leave-to-class="opacity-0"
        >
          <ListboxOptions class="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-gray-200 bg-white py-1 shadow-lg focus:outline-none">
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
                  active ? 'bg-gray-100 text-gray-900' : 'text-gray-900'
                ]"
              >
                <span :class="['block truncate', selected ? 'font-semibold' : 'font-normal']">
                  {{ option.label }}
                </span>
                <component
                  v-if="selected"
                  :is="Check"
                  class="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-900"
                />
              </li>
            </ListboxOption>
          </ListboxOptions>
        </Transition>
      </div>
    </Listbox>
    <p v-if="error" class="mt-1.5 text-sm text-red-600">
      {{ error }}
    </p>
    <p v-else-if="hint" class="mt-1.5 text-sm text-gray-500">
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

const baseClasses = 'relative w-full h-10 px-3 pr-10 rounded-lg border focus-ring disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-between'
const stateClasses = computed(() => {
  if (props.error) return 'border-red-300 bg-red-50'
  return 'border-gray-300 bg-white text-gray-900'
})

const buttonClasses = computed(() => cn(baseClasses, stateClasses.value))
</script>
