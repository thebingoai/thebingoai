<template>
  <div class="w-full">
    <label v-if="label" :for="id" class="mb-1.5 block text-sm font-light text-gray-700">
      {{ label }}
      <span v-if="required" class="text-red-600">*</span>
    </label>
    <div class="relative">
      <div v-if="$slots.prefix || prefixIcon" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2">
        <component v-if="prefixIcon" :is="prefixIcon" class="h-5 w-5 text-gray-400" />
        <slot v-else name="prefix" />
      </div>
      <input
        :id="id"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :required="required"
        :class="inputClasses"
        @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        @blur="$emit('blur', $event)"
        @focus="$emit('focus', $event)"
      />
      <div v-if="$slots.suffix || suffixIcon" class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2">
        <component v-if="suffixIcon" :is="suffixIcon" class="h-5 w-5 text-gray-400" />
        <slot v-else name="suffix" />
      </div>
    </div>
    <p v-if="error" class="mt-1.5 text-sm text-red-600">
      {{ error }}
    </p>
    <p v-else-if="hint" class="mt-1.5 text-sm text-gray-500">
      {{ hint }}
    </p>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { cn } from '~/utils/cn'

interface Props {
  modelValue?: string | number
  type?: 'text' | 'email' | 'password' | 'number' | 'url' | 'search'
  label?: string
  placeholder?: string
  error?: string
  hint?: string
  disabled?: boolean
  required?: boolean
  prefixIcon?: Component
  suffixIcon?: Component
  id?: string
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  disabled: false,
  required: false
})

defineEmits<{
  'update:modelValue': [value: string]
  blur: [event: FocusEvent]
  focus: [event: FocusEvent]
}>()

const id = props.id || `input-${Math.random().toString(36).substr(2, 9)}`

const baseClasses = 'w-full h-10 px-3 rounded-lg border focus-ring disabled:opacity-50 disabled:cursor-not-allowed'
const stateClasses = computed(() => {
  if (props.error) return 'border-red-300 bg-red-50'
  return 'border-gray-300 bg-white'
})
const slots = useSlots()
const paddingClasses = computed(() => {
  let classes = ''
  if (props.prefixIcon || slots.prefix) classes += 'pl-10 '
  if (props.suffixIcon || slots.suffix) classes += 'pr-10'
  return classes
})

const inputClasses = computed(() =>
  cn(
    baseClasses,
    stateClasses.value,
    paddingClasses.value,
    'text-gray-900 placeholder:text-gray-400'
  )
)
</script>
