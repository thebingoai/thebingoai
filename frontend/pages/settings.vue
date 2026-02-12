<template>
  <div class="container mx-auto p-6">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
        Settings
      </h1>
      <p class="mt-2 text-neutral-600 dark:text-neutral-400">
        Configure your LLM-MD-CLI preferences
      </p>
    </div>

    <!-- Settings Content -->
    <div class="grid gap-6 lg:grid-cols-4">
      <!-- Sidebar Navigation -->
      <div class="lg:col-span-1">
        <nav class="sticky top-24 space-y-1 rounded-lg border border-neutral-200 bg-white p-2 dark:border-neutral-800 dark:bg-neutral-900">
          <button
            v-for="section in sections"
            :key="section.id"
            @click="activeSection = section.id"
            class="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors"
            :class="{
              'bg-brand-100 text-brand-700 dark:bg-brand-900/20 dark:text-brand-400': activeSection === section.id,
              'text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800': activeSection !== section.id
            }"
          >
            <component :is="section.icon" class="h-4 w-4" />
            {{ section.label }}
          </button>
        </nav>
      </div>

      <!-- Settings Panel -->
      <div class="lg:col-span-3">
        <div class="rounded-lg border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900">
          <GeneralSettings v-if="activeSection === 'general'" />
          <AppearanceSettings v-if="activeSection === 'appearance'" />
          <AboutSection v-if="activeSection === 'about'" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Settings as SettingsIcon, Palette, Info } from 'lucide-vue-next'

const activeSection = ref('general')

const sections = [
  { id: 'general', label: 'General', icon: SettingsIcon },
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'about', label: 'About', icon: Info }
]
</script>
