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
        <div class="flex min-h-full items-end justify-center">
          <TransitionChild
            as="template"
            enter="duration-300 ease-out"
            enter-from="opacity-0 translate-y-full"
            enter-to="opacity-100 translate-y-0"
            leave="duration-200 ease-in"
            leave-from="opacity-100 translate-y-0"
            leave-to="opacity-0 translate-y-full"
          >
            <DialogPanel class="fixed inset-x-0 bottom-0 w-full transform overflow-hidden rounded-t-2xl bg-white text-left align-middle shadow-xl transition-all max-h-[80vh]">
              <!-- Drag handle -->
              <div class="flex justify-center py-3 border-b border-gray-200">
                <div class="w-12 h-1 bg-gray-300 rounded-full" />
              </div>

              <div v-if="title || $slots.header" class="flex items-center justify-between border-b border-gray-200 px-6 py-4">
                <DialogTitle v-if="title" class="text-lg font-normal text-gray-900">
                  {{ title }}
                </DialogTitle>
                <slot v-else name="header" />
                <button
                  v-if="closable"
                  @click="$emit('update:open', false)"
                  class="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                >
                  <component :is="X" class="h-5 w-5" />
                </button>
              </div>

              <div class="px-6 py-4 overflow-y-auto">
                <slot />
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

interface Props {
  open: boolean
  title?: string
  closable?: boolean
}

withDefaults(defineProps<Props>(), {
  closable: true
})

defineEmits<{
  'update:open': [value: boolean]
}>()
</script>
