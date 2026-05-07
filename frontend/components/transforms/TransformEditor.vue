<template>
  <UiDialog :open="open" title="New Transform" size="lg" @update:open="$emit('update:open', $event)">
    <form @submit.prevent="handleSubmit" class="space-y-5">
      <!-- Name -->
      <UiInput
        v-model="form.name"
        label="Name"
        placeholder="e.g. daily_revenue_summary"
        required
        :error="formErrors.name"
      />

      <!-- SQL -->
      <div>
        <label class="mb-1.5 block text-sm font-light text-gray-700 dark:text-neutral-300">
          SQL <span class="text-red-600">*</span>
        </label>
        <textarea
          v-model="form.sql"
          rows="10"
          spellcheck="false"
          placeholder="SELECT ..."
          class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:placeholder:text-neutral-500 dark:focus:ring-neutral-400 font-mono resize-y"
          :class="{ 'border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-950': formErrors.sql }"
        />
        <p v-if="formErrors.sql" class="mt-1.5 text-sm text-red-600">{{ formErrors.sql }}</p>
      </div>

      <!-- Materialization -->
      <div>
        <label class="mb-1.5 block text-sm font-light text-gray-700 dark:text-neutral-300">Materialization</label>
        <div class="flex rounded-lg border border-gray-300 dark:border-neutral-600 overflow-hidden w-fit">
          <button
            v-for="opt in materializationOptions"
            :key="opt"
            type="button"
            class="px-4 py-2 text-sm transition-colors border-l border-gray-300 dark:border-neutral-600 first:border-l-0 capitalize"
            :class="form.materialization === opt
              ? 'bg-gray-900 text-white dark:bg-neutral-100 dark:text-neutral-900'
              : 'bg-white text-gray-600 hover:bg-gray-50 dark:bg-neutral-800 dark:text-neutral-400 dark:hover:bg-neutral-700'"
            @click="form.materialization = opt"
          >
            {{ opt }}
          </button>
        </div>
      </div>

      <!-- Unique Key (shown only for incremental) -->
      <UiInput
        v-if="form.materialization === 'incremental'"
        v-model="form.unique_key"
        label="Unique Key"
        placeholder="e.g. id"
        hint="Column(s) used to detect new or updated rows."
        :error="formErrors.unique_key"
      />

      <!-- Cron -->
      <UiInput
        v-model="form.cron"
        label="Cron Schedule"
        placeholder="e.g. 0 3 * * * (daily at 3 AM UTC)"
        hint="Leave blank to run manually only."
      />

      <!-- Submit error -->
      <p v-if="submitError" class="text-sm text-red-600">{{ submitError }}</p>
    </form>

    <template #footer>
      <UiButton variant="outline" @click="$emit('update:open', false)" :disabled="submitting">
        Cancel
      </UiButton>
      <UiButton type="submit" :loading="submitting" @click="handleSubmit">
        Create Transform
      </UiButton>
    </template>
  </UiDialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { useAuthStore } from '~/stores/auth'
import { useUserTransforms, type Transform, type CreateTransformPayload } from '~/composables/useUserTransforms'

const props = defineProps<{
  open: boolean
  modelValue?: Transform | null
  ownerScopeKind?: string
  ownerScopeId?: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'update:modelValue': [value: Transform | null]
  'created': [transform: Transform]
  'updated': [transform: Transform]
}>()

const authStore = useAuthStore()
const { createTransform } = useUserTransforms()

const materializationOptions = ['table', 'view', 'incremental'] as const

const submitting = ref(false)
const submitError = ref<string | null>(null)

const form = reactive({
  name: '',
  sql: '',
  materialization: 'table' as 'table' | 'view' | 'incremental',
  unique_key: '',
  cron: '',
})

const formErrors = reactive({
  name: '',
  sql: '',
  unique_key: '',
})

function resetForm() {
  form.name = ''
  form.sql = ''
  form.materialization = 'table'
  form.unique_key = ''
  form.cron = ''
  submitError.value = null
  Object.keys(formErrors).forEach(k => { (formErrors as Record<string, string>)[k] = '' })
}

watch(() => props.open, (val) => {
  if (val) resetForm()
})

function validate(): boolean {
  let valid = true
  Object.keys(formErrors).forEach(k => { (formErrors as Record<string, string>)[k] = '' })

  if (!form.name.trim()) {
    formErrors.name = 'Name is required.'
    valid = false
  }
  if (!form.sql.trim()) {
    formErrors.sql = 'SQL is required.'
    valid = false
  }
  if (form.materialization === 'incremental' && !form.unique_key.trim()) {
    formErrors.unique_key = 'Unique key is required for incremental materialization.'
    valid = false
  }

  return valid
}

async function handleSubmit() {
  if (!validate()) return

  submitting.value = true
  submitError.value = null

  try {
    const user = authStore.currentUser
    const payload: CreateTransformPayload = {
      name: form.name.trim(),
      sql: form.sql.trim(),
      materialization: form.materialization,
      owner_scope_kind: props.ownerScopeKind ?? 'user',
      owner_scope_id: props.ownerScopeId ?? (user?.id ?? ''),
    }

    if (form.cron.trim()) {
      payload.cron = form.cron.trim()
    }
    if (form.materialization === 'incremental' && form.unique_key.trim()) {
      payload.unique_key = form.unique_key.trim()
    }

    const result = await createTransform(payload)
    emit('created', result)
    emit('update:open', false)
  } catch (e: unknown) {
    submitError.value = e instanceof Error ? e.message : 'Failed to create transform.'
  } finally {
    submitting.value = false
  }
}
</script>
