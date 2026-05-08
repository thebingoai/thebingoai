<template>
  <TransitionRoot :show="open" as="template">
    <Dialog as="div" class="relative z-50" @close="handleClose">
      <TransitionChild
        as="template"
        enter="duration-200 ease-out"
        enter-from="opacity-0 scale-[0.99]"
        enter-to="opacity-100 scale-100"
        leave="duration-150 ease-in"
        leave-from="opacity-100 scale-100"
        leave-to="opacity-0 scale-[0.99]"
      >
        <DialogPanel class="fixed inset-0 bg-white dark:bg-neutral-900 flex flex-col overflow-hidden">
          <div
            v-if="$slots.header"
            class="shrink-0 border-b border-gray-200 dark:border-neutral-700 px-6 py-4"
          >
            <slot name="header" />
          </div>

          <div class="flex-1 overflow-y-auto">
            <slot />
          </div>

          <div
            v-if="$slots.footer"
            class="shrink-0"
          >
            <slot name="footer" />
          </div>
        </DialogPanel>
      </TransitionChild>
    </Dialog>
  </TransitionRoot>
</template>

<script setup lang="ts">
import { Dialog, DialogPanel, TransitionRoot, TransitionChild } from '@headlessui/vue'

interface Props {
  open: boolean
  closable?: boolean
}

const props = withDefaults(defineProps<Props>(), { closable: true })

const emit = defineEmits<{ 'update:open': [value: boolean] }>()

function handleClose() {
  if (props.closable) emit('update:open', false)
}
</script>
