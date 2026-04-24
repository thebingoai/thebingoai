<template>
  <div class="p-6 space-y-6">
    <div class="space-y-2">
      <h2 class="text-2xl font-medium text-gray-900 dark:text-white">API Keys</h2>
      <p class="text-sm text-gray-500 dark:text-neutral-400">
        Provider keys are read from the server's <code class="text-xs px-1 py-0.5 rounded bg-gray-100 dark:bg-neutral-800">.env</code> file. Contact your administrator to add or change keys.
      </p>
    </div>

    <div class="rounded-xl border border-gray-200 dark:border-neutral-700 divide-y divide-gray-100 dark:divide-neutral-700">
      <div
        v-for="(info, name) in providers"
        :key="name"
        class="flex items-center justify-between px-6 py-4 gap-4"
      >
        <div class="min-w-0">
          <p class="text-sm font-medium text-gray-900 dark:text-white">{{ displayName(name) }}</p>
          <p class="text-xs text-gray-400 dark:text-neutral-500 font-mono truncate">{{ info.base_url }}</p>
        </div>
        <span
          v-if="info.configured"
          class="shrink-0 inline-flex items-center gap-1.5 text-xs font-medium text-green-600 dark:text-green-400"
        >
          <span class="h-1.5 w-1.5 rounded-full bg-green-500" />
          Configured
        </span>
        <span v-else class="shrink-0 text-xs text-gray-400 dark:text-neutral-500">
          Not configured — set <code class="text-xs px-1 py-0.5 rounded bg-gray-100 dark:bg-neutral-800">{{ envVarName(name) }}</code> in .env
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const { config: featureConfig } = useFeatureConfig()
const providers = computed(() => featureConfig.value?.providers ?? {})

const displayNames: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
}

function displayName(name: string): string {
  return displayNames[name] ?? name
}

function envVarName(name: string): string {
  return `${name.toUpperCase()}_API_KEY`
}
</script>
