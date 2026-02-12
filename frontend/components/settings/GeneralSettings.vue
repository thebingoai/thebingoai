<template>
  <div class="space-y-6">
    <div>
      <h3 class="mb-4 text-lg font-semibold text-neutral-900 dark:text-neutral-100">
        General Settings
      </h3>

      <div class="space-y-4">
        <!-- Backend URL -->
        <UiInput
          v-model="settings.backendUrl"
          label="Backend URL"
          placeholder="http://localhost:8000"
          hint="The URL of your LLM-MD-CLI backend"
        />

        <!-- Test Connection -->
        <div>
          <UiButton @click="testConnection" :loading="testing">
            <component :is="Activity" class="h-4 w-4" />
            Test Connection
          </UiButton>
          <p v-if="connectionResult" class="mt-2 text-sm" :class="connectionResult.success ? 'text-success-600 dark:text-success-400' : 'text-error-600 dark:text-error-400'">
            {{ connectionResult.message }}
          </p>
        </div>

        <!-- Default Namespace -->
        <UiSelect
          v-model="settings.defaultNamespace"
          :options="namespaceOptions"
          label="Default Namespace"
          hint="The namespace to use by default for uploads and queries"
        />

        <!-- Default Provider -->
        <UiSelect
          v-model="settings.defaultProvider"
          :options="providerOptions"
          label="Default LLM Provider"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Activity } from 'lucide-vue-next'
import { toast } from 'vue-sonner'

const settings = useSettingsStore()
const { namespaceNames } = useNamespaces()
const api = useApi()

const testing = ref(false)
const connectionResult = ref<{ success: boolean; message: string } | null>(null)

const namespaceOptions = computed(() =>
  namespaceNames.value.map(ns => ({ label: ns, value: ns }))
)

const providerOptions = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'Ollama', value: 'ollama' }
]

const testConnection = async () => {
  testing.value = true
  connectionResult.value = null

  try {
    await api.getHealth()
    connectionResult.value = {
      success: true,
      message: 'Connection successful!'
    }
    settings.setConnectionStatus('connected')
    toast.success('Connected to backend')
  } catch (error: any) {
    connectionResult.value = {
      success: false,
      message: error.message || 'Connection failed'
    }
    settings.setConnectionStatus('disconnected')
    toast.error('Failed to connect to backend')
  } finally {
    testing.value = false
  }
}
</script>
