<template>
  <div class="space-y-6">
    <div>
      <h3 class="mb-4 text-lg font-semibold text-neutral-900 dark:text-neutral-100">
        Appearance
      </h3>

      <div class="space-y-6">
        <!-- Theme -->
        <div>
          <label class="mb-3 block text-sm font-medium text-neutral-700 dark:text-neutral-300">
            Theme
          </label>
          <div class="grid grid-cols-3 gap-3">
            <button
              v-for="theme in themes"
              :key="theme.value"
              @click="colorMode.preference = theme.value"
              class="flex flex-col items-center gap-2 rounded-lg border-2 p-4 transition-all"
              :class="{
                'border-brand-600 bg-brand-50 dark:border-brand-400 dark:bg-brand-900/20': colorMode.preference === theme.value,
                'border-neutral-200 hover:border-neutral-300 dark:border-neutral-700 dark:hover:border-neutral-600': colorMode.preference !== theme.value
              }"
            >
              <component :is="theme.icon" class="h-6 w-6 text-neutral-600 dark:text-neutral-400" />
              <span class="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                {{ theme.label }}
              </span>
            </button>
          </div>
        </div>

        <!-- Font Size -->
        <div>
          <label class="mb-3 block text-sm font-medium text-neutral-700 dark:text-neutral-300">
            Font Size
          </label>
          <div class="flex gap-2">
            <button
              v-for="size in fontSizes"
              :key="size.value"
              @click="settings.setFontSize(size.value)"
              class="flex-1 rounded-lg border-2 px-4 py-2 text-sm font-medium transition-all"
              :class="{
                'border-brand-600 bg-brand-50 dark:border-brand-400 dark:bg-brand-900/20': settings.fontSize === size.value,
                'border-neutral-200 hover:border-neutral-300 dark:border-neutral-700 dark:hover:border-neutral-600': settings.fontSize !== size.value
              }"
            >
              {{ size.label }}
            </button>
          </div>
        </div>

        <!-- Density -->
        <div>
          <label class="mb-3 block text-sm font-medium text-neutral-700 dark:text-neutral-300">
            Layout Density
          </label>
          <div class="flex gap-2">
            <button
              v-for="density in densities"
              :key="density.value"
              @click="settings.setDensity(density.value)"
              class="flex-1 rounded-lg border-2 px-4 py-2 text-sm font-medium transition-all"
              :class="{
                'border-brand-600 bg-brand-50 dark:border-brand-400 dark:bg-brand-900/20': settings.density === density.value,
                'border-neutral-200 hover:border-neutral-300 dark:border-neutral-700 dark:hover:border-neutral-600': settings.density !== density.value
              }"
            >
              {{ density.label }}
            </button>
          </div>
        </div>

        <!-- Animations -->
        <div class="flex items-center justify-between">
          <div>
            <label class="text-sm font-medium text-neutral-700 dark:text-neutral-300">
              Enable Animations
            </label>
            <p class="text-sm text-neutral-500 dark:text-neutral-400">
              Show transition and loading animations
            </p>
          </div>
          <input
            type="checkbox"
            :checked="settings.animationsEnabled"
            @change="settings.setAnimationsEnabled(!settings.animationsEnabled)"
            class="h-5 w-5 rounded border-neutral-300 text-brand-600 focus:ring-brand-500 dark:border-neutral-700"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Sun, Moon, Monitor } from 'lucide-vue-next'
import type { FontSize, LayoutDensity } from '~/types'

const settings = useSettingsStore()
const colorMode = useColorMode()

const themes = [
  { label: 'Light', value: 'light', icon: Sun },
  { label: 'Dark', value: 'dark', icon: Moon },
  { label: 'System', value: 'system', icon: Monitor }
]

const fontSizes: Array<{ label: string; value: FontSize }> = [
  { label: 'Small', value: 'small' },
  { label: 'Medium', value: 'medium' },
  { label: 'Large', value: 'large' }
]

const densities: Array<{ label: string; value: LayoutDensity }> = [
  { label: 'Comfortable', value: 'comfortable' },
  { label: 'Compact', value: 'compact' }
]
</script>
