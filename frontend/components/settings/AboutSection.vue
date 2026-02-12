<template>
  <div class="space-y-6">
    <div>
      <h3 class="mb-4 text-lg font-semibold text-neutral-900 dark:text-neutral-100">
        About
      </h3>

      <div class="rounded-lg border border-neutral-200 bg-neutral-50 p-6 dark:border-neutral-700 dark:bg-neutral-800">
        <div class="mb-4 flex items-center gap-3">
          <div class="rounded-lg bg-brand-100 p-3 dark:bg-brand-900/20">
            <component :is="FileText" class="h-8 w-8 text-brand-600 dark:text-brand-400" />
          </div>
          <div>
            <h4 class="text-xl font-bold text-neutral-900 dark:text-neutral-100">
              LLM-MD-CLI
            </h4>
            <p class="text-sm text-neutral-600 dark:text-neutral-400">
              Version 1.0.0
            </p>
          </div>
        </div>

        <p class="mb-4 text-sm text-neutral-700 dark:text-neutral-300">
          A RAG (Retrieval-Augmented Generation) system for indexing and querying markdown files using LLMs.
        </p>

        <div class="space-y-2 text-sm">
          <div class="flex items-center justify-between">
            <span class="text-neutral-600 dark:text-neutral-400">Framework</span>
            <span class="font-medium text-neutral-900 dark:text-neutral-100">Nuxt 4 + Vue 3</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-neutral-600 dark:text-neutral-400">State Management</span>
            <span class="font-medium text-neutral-900 dark:text-neutral-100">Pinia</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-neutral-600 dark:text-neutral-400">Styling</span>
            <span class="font-medium text-neutral-900 dark:text-neutral-100">Tailwind CSS</span>
          </div>
        </div>

        <div class="mt-6 flex gap-3">
          <a
            href="https://github.com/yourusername/llm-md-cli"
            target="_blank"
            class="flex items-center gap-2 text-sm text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
          >
            <component :is="Github" class="h-4 w-4" />
            GitHub
          </a>
          <a
            href="https://github.com/yourusername/llm-md-cli/issues"
            target="_blank"
            class="flex items-center gap-2 text-sm text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
          >
            <component :is="Bug" class="h-4 w-4" />
            Report Issue
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { FileText, Github, Bug } from 'lucide-vue-next'
</script>
