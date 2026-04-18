<template>
  <Menu as="div" class="relative inline-block text-left">
    <MenuButton as="template">
      <slot name="trigger" />
    </MenuButton>

    <Transition
      enter-active-class="transition duration-100 ease-out"
      enter-from-class="transform scale-95 opacity-0"
      enter-to-class="transform scale-100 opacity-100"
      leave-active-class="transition duration-75 ease-in"
      leave-from-class="transform scale-100 opacity-100"
      leave-to-class="transform scale-95 opacity-0"
    >
      <MenuItems :class="menuClasses">
        <div class="py-1">
          <MenuItem
            v-for="(item, index) in items"
            :key="index"
            v-slot="{ active }"
            as="template"
          >
            <button
              :class="[
                'flex w-full items-center gap-3 px-4 py-2 text-sm',
                active ? 'bg-gray-100 text-gray-900 dark:bg-neutral-700 dark:text-neutral-100' : 'text-gray-700 dark:text-neutral-300',
                item.danger && 'text-red-600'
              ]"
              @click="item.onClick"
            >
              <component v-if="item.icon" :is="item.icon" class="h-4 w-4" />
              {{ item.label }}
            </button>
          </MenuItem>
        </div>
      </MenuItems>
    </Transition>
  </Menu>
</template>

<script setup lang="ts">
import { Menu, MenuButton, MenuItems, MenuItem } from '@headlessui/vue'
import type { Component } from 'vue'
import { cn } from '~/utils/cn'

export interface DropdownItem {
  label: string
  icon?: Component
  onClick: () => void
  danger?: boolean
}

interface Props {
  items: DropdownItem[]
  align?: 'left' | 'right'
}

const props = withDefaults(defineProps<Props>(), {
  align: 'right'
})

const alignClasses = {
  left: 'left-0 origin-top-left',
  right: 'right-0 origin-top-right'
}

const menuClasses = computed(() =>
  cn(
    'absolute z-10 mt-2 w-56 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-lg focus:outline-none',
    alignClasses[props.align]
  )
)
</script>
