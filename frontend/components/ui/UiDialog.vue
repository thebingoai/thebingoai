<template>
  <TransitionRoot :show="open" as="template">
    <Dialog as="div" class="relative z-50" @close="$emit('update:open', false)">
      <TransitionChild
        as="template"
        enter="duration-300 ease-out"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="duration-200 ease-in"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <div class="fixed inset-0 bg-black/50" />
      </TransitionChild>

      <div class="fixed inset-0 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4">
          <TransitionChild
            as="template"
            enter="duration-300 ease-out"
            enter-from="opacity-0 scale-95"
            enter-to="opacity-100 scale-100"
            leave="duration-200 ease-in"
            leave-from="opacity-100 scale-100"
            leave-to="opacity-0 scale-95"
          >
            <DialogPanel :class="panelClasses">
              <div v-if="title || $slots.header" class="flex items-center justify-between border-b border-gray-200 dark:border-neutral-700 px-6 py-4">
                <DialogTitle v-if="title" class="text-lg font-normal text-gray-900 dark:text-neutral-100">
                  {{ title }}
                </DialogTitle>
                <slot v-else name="header" />
                <button
                  v-if="closable"
                  @click="$emit('update:open', false)"
                  class="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-neutral-400 dark:hover:bg-neutral-700 dark:hover:text-neutral-200"
                >
                  <component :is="X" class="h-5 w-5" />
                </button>
              </div>

              <div class="px-6 py-4">
                <slot />
              </div>

              <div v-if="$slots.footer" class="flex items-center justify-end gap-3 border-t border-gray-200 dark:border-neutral-700 px-6 py-4">
                <slot name="footer" />
              </div>
            </DialogPanel>
          </TransitionChild>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>

<script setup lang="ts">
import { Dialog, DialogPanel, DialogTitle, TransitionRoot, TransitionChild } from '@headlessui/vue'
import { X } from 'lucide-vue-next'
import { cn } from '~/utils/cn'

interface Props {
  open: boolean
  title?: string
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
  closable?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
  closable: true
})

defineEmits<{
  'update:open': [value: boolean]
}>()

const sizeClasses = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
  full: 'max-w-full mx-4'
}

const panelClasses = computed(() =>
  cn(
    'w-full transform overflow-hidden rounded-lg bg-white dark:bg-neutral-800 text-left align-middle shadow-xl',
    sizeClasses[props.size]
  )
)
</script>
