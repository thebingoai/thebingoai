<template>
  <UiDialog :open="open" title="New Pipeline" size="lg" @update:open="$emit('update:open', $event)">
    <form @submit.prevent="handleSubmit" class="space-y-5">
      <!-- Name -->
      <UiInput
        v-model="form.name"
        label="Name"
        placeholder="e.g. Daily Salesforce Sync"
        required
        :error="formErrors.name"
      />

      <!-- Source Connection -->
      <div class="w-full">
        <label class="mb-1.5 block text-sm font-light text-gray-700 dark:text-neutral-300">
          Source Connection <span class="text-red-600">*</span>
        </label>
        <select
          v-model="form.source_connection_id"
          class="w-full h-10 px-3 rounded-lg border border-gray-300 bg-white text-gray-900 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-neutral-400 text-sm"
          required
        >
          <option value="" disabled>Select a connection…</option>
          <option
            v-for="conn in connections"
            :key="conn.id"
            :value="conn.id"
          >
            {{ conn.name }}
          </option>
        </select>
        <p v-if="formErrors.source_connection_id" class="mt-1.5 text-sm text-red-600">
          {{ formErrors.source_connection_id }}
        </p>
      </div>

      <!-- Target Table -->
      <UiInput
        v-model="form.target_table"
        label="Target Table"
        placeholder="e.g. salesforce_accounts"
        required
        hint="The destination table name in the data lake."
        :error="formErrors.target_table"
      />

      <!-- Mode toggle -->
      <div>
        <label class="mb-1.5 block text-sm font-light text-gray-700 dark:text-neutral-300">Mode</label>
        <div class="flex rounded-lg border border-gray-300 dark:border-neutral-600 overflow-hidden w-fit">
          <button
            type="button"
            class="px-4 py-2 text-sm transition-colors"
            :class="form.mode === 'full'
              ? 'bg-gray-900 text-white dark:bg-neutral-100 dark:text-neutral-900'
              : 'bg-white text-gray-600 hover:bg-gray-50 dark:bg-neutral-800 dark:text-neutral-400 dark:hover:bg-neutral-700'"
            @click="form.mode = 'full'"
          >
            Full
          </button>
          <button
            type="button"
            class="px-4 py-2 text-sm transition-colors border-l border-gray-300 dark:border-neutral-600"
            :class="form.mode === 'incremental'
              ? 'bg-gray-900 text-white dark:bg-neutral-100 dark:text-neutral-900'
              : 'bg-white text-gray-600 hover:bg-gray-50 dark:bg-neutral-800 dark:text-neutral-400 dark:hover:bg-neutral-700'"
            @click="form.mode = 'incremental'"
          >
            Incremental
          </button>
        </div>
        <p class="mt-1.5 text-xs text-gray-500 dark:text-neutral-500">
          <template v-if="form.mode === 'full'">Replaces all rows on each run.</template>
          <template v-else>Appends only new/changed rows using the incremental key.</template>
        </p>
      </div>

      <!-- Incremental Key (shown only when mode = incremental) -->
      <UiInput
        v-if="form.mode === 'incremental'"
        v-model="form.incremental_key"
        label="Incremental Key"
        placeholder="e.g. updated_at"
        hint="Column used to detect new or updated rows."
        :error="formErrors.incremental_key"
      />

      <!-- Cron -->
      <UiInput
        v-model="form.cron"
        label="Cron Schedule"
        placeholder="e.g. 0 3 * * * (daily at 3 AM UTC)"
        hint="Leave blank to run manually only."
      />

      <!-- Extraction Config -->
      <div>
        <label class="mb-1.5 block text-sm font-light text-gray-700 dark:text-neutral-300">
          Extraction Config (JSON)
        </label>
        <textarea
          v-model="extractionConfigText"
          rows="4"
          placeholder="{}"
          class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:placeholder:text-neutral-500 dark:focus:ring-neutral-400 font-mono"
        />
        <p v-if="formErrors.extraction_config" class="mt-1.5 text-sm text-red-600">
          {{ formErrors.extraction_config }}
        </p>
        <p v-else class="mt-1.5 text-xs text-gray-500 dark:text-neutral-500">
          Connector-specific extraction options as JSON.
        </p>
      </div>

      <!-- Submit error -->
      <p v-if="submitError" class="text-sm text-red-600">{{ submitError }}</p>
    </form>

    <template #footer>
      <UiButton variant="outline" @click="$emit('update:open', false)" :disabled="submitting">
        Cancel
      </UiButton>
      <UiButton type="submit" :loading="submitting" @click="handleSubmit">
        Create Pipeline
      </UiButton>
    </template>
  </UiDialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import { useUserPipelines, type CreatePipelinePayload } from '~/composables/useUserPipelines'
import { useApi } from '~/composables/useApi'

interface Connection {
  id: number
  name: string
  db_type: string
}

const props = defineProps<{
  open: boolean
  ownerScopeKind?: string
  ownerScopeId?: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'created': [pipeline: unknown]
}>()

const { createPipeline } = useUserPipelines()
const api = useApi()

const connections = ref<Connection[]>([])
const submitting = ref(false)
const submitError = ref<string | null>(null)

const form = reactive({
  name: '',
  source_connection_id: '' as number | '',
  target_table: '',
  mode: 'full' as 'full' | 'incremental',
  incremental_key: '',
  cron: '',
})

const extractionConfigText = ref('{}')

const formErrors = reactive({
  name: '',
  source_connection_id: '',
  target_table: '',
  incremental_key: '',
  extraction_config: '',
})

function resetForm() {
  form.name = ''
  form.source_connection_id = ''
  form.target_table = ''
  form.mode = 'full'
  form.incremental_key = ''
  form.cron = ''
  extractionConfigText.value = '{}'
  submitError.value = null
  Object.keys(formErrors).forEach(k => { (formErrors as any)[k] = '' })
}

watch(() => props.open, (val) => {
  if (val) resetForm()
})

onMounted(async () => {
  try {
    const data = await (api as any).connections.list()
    connections.value = Array.isArray(data) ? data : (data?.connections ?? [])
  } catch {
    // silently fail — user will see empty dropdown
  }
})

function validate(): boolean {
  let valid = true
  Object.keys(formErrors).forEach(k => { (formErrors as any)[k] = '' })

  if (!form.name.trim()) {
    formErrors.name = 'Name is required.'
    valid = false
  }
  if (!form.source_connection_id) {
    formErrors.source_connection_id = 'Please select a source connection.'
    valid = false
  }
  if (!form.target_table.trim()) {
    formErrors.target_table = 'Target table is required.'
    valid = false
  }
  if (form.mode === 'incremental' && !form.incremental_key.trim()) {
    formErrors.incremental_key = 'Incremental key is required for incremental mode.'
    valid = false
  }

  let parsedConfig: Record<string, unknown> = {}
  try {
    parsedConfig = JSON.parse(extractionConfigText.value || '{}')
    if (typeof parsedConfig !== 'object' || Array.isArray(parsedConfig)) {
      formErrors.extraction_config = 'Extraction config must be a JSON object.'
      valid = false
    }
  } catch {
    formErrors.extraction_config = 'Invalid JSON.'
    valid = false
  }

  return valid
}

async function handleSubmit() {
  if (!validate()) return

  submitting.value = true
  submitError.value = null

  try {
    const payload: CreatePipelinePayload = {
      name: form.name.trim(),
      source_connection_id: form.source_connection_id as number,
      owner_scope_kind: props.ownerScopeKind ?? 'user',
      owner_scope_id: props.ownerScopeId ?? '',
      target_table: form.target_table.trim(),
      mode: form.mode,
      extraction_config: JSON.parse(extractionConfigText.value || '{}'),
    }

    if (form.cron.trim()) {
      payload.cron = form.cron.trim()
    }
    if (form.mode === 'incremental' && form.incremental_key.trim()) {
      payload.incremental_key = form.incremental_key.trim()
    }

    const pipeline = await createPipeline(payload)
    emit('created', pipeline)
    emit('update:open', false)
  } catch (e: unknown) {
    submitError.value = e instanceof Error ? e.message : 'Failed to create pipeline.'
  } finally {
    submitting.value = false
  }
}
</script>
