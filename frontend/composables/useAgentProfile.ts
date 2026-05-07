import { ref, computed } from 'vue'
import { useAuthStore } from '~/stores/auth'
import { createFetchHelper } from '~/utils/api/fetchHelper'

export interface UserProfileFields {
  address_as: string
  pronouns: string
  role: string
  team: string
  timezone: string
  working_hours: string
}

export interface VocabItem {
  term: string
  definition: string
}

export interface AgentProfileData {
  display_name: string
  pronouns: string
  tagline: string
  avatar_url: string | null
  default_model: string
  temperature: number
  max_output_tokens: number
  soul: string
  user_profile: UserProfileFields
  user_narrative: string
  vocabulary: VocabItem[]
  sensitivities: string[]
  version: number
  published_version: number | null
  published_at: string | null
}

export interface ProviderModels {
  name: string
  available: boolean
  default_model: string | null
  models: string[]
}

export interface ModelsResponse {
  default_provider: string
  default_model: string | null
  providers: ProviderModels[]
}

export function useAgentProfile() {
  const authStore = useAuthStore()
  const router = useRouter()
  const { fetchWithRefresh } = createFetchHelper(authStore, router)

  const profile    = ref<AgentProfileData | null>(null)
  const models     = ref<ModelsResponse | null>(null)
  const loading    = ref(false)
  const saving     = ref(false)
  const publishing = ref(false)
  const saveError  = ref<string | null>(null)

  // Track which top-level sections have unsaved changes since last publish
  const changedSections = ref<Set<string>>(new Set())

  let _pendingFields: Partial<AgentProfileData> = {}
  let _saveTimer: ReturnType<typeof setTimeout> | null = null

  // Bumped on every reset/publish/fetch — _doSave drops responses tagged with a
  // stale token so an in-flight PATCH can't clobber a freshly reverted state.
  let _opToken = 0

  async function fetchProfile() {
    loading.value = true
    saveError.value = null
    try {
      const data = await fetchWithRefresh<AgentProfileData>('/api/agent-profile')
      profile.value = data
    } catch (e: any) {
      saveError.value = e?.data?.detail ?? e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchModels() {
    try {
      models.value = await fetchWithRefresh<ModelsResponse>('/api/llm/models')
    } catch {
      // Non-fatal: dropdown falls back to whatever value the profile holds
    }
  }

  // Call whenever the user edits fields in a section.
  // `section` is one of: 'identity' | 'soul' | 'user-context'
  // `fields` is the partial patch to send to the API.
  function updateField(section: string, fields: Partial<AgentProfileData>) {
    if (!profile.value) return
    Object.assign(profile.value, fields)
    changedSections.value = new Set([...changedSections.value, section])
    _scheduleSave(fields)
  }

  function _scheduleSave(fields: Partial<AgentProfileData>) {
    Object.assign(_pendingFields, fields)
    if (_saveTimer) clearTimeout(_saveTimer)
    _saveTimer = setTimeout(() => {
      const batch = { ..._pendingFields }
      _pendingFields = {}
      _doSave(batch)
    }, 800)
  }

  async function _doSave(fields: Partial<AgentProfileData>) {
    if (!profile.value) return
    const tokenAtSend = _opToken
    saving.value = true
    try {
      const updated = await fetchWithRefresh<AgentProfileData>('/api/agent-profile', {
        method: 'PATCH',
        body: fields,
      })
      // If a reset (or other op) ran while we were in flight, drop the response.
      if (tokenAtSend !== _opToken) return
      // Guard against stale responses arriving out of order
      if (profile.value && updated.version > profile.value.version) {
        profile.value.version = updated.version
      }
      saveError.value = null
    } catch (e: any) {
      if (tokenAtSend !== _opToken) return
      saveError.value = e?.data?.detail ?? e.message
    } finally {
      saving.value = false
    }
  }

  async function publish() {
    publishing.value = true
    saveError.value = null
    try {
      await fetchWithRefresh('/api/agent-profile/publish', { method: 'POST' })
      if (profile.value) {
        profile.value.published_version = profile.value.version
        profile.value.published_at = new Date().toISOString()
      }
      changedSections.value = new Set()
    } catch (e: any) {
      saveError.value = e?.data?.detail ?? e.message
    } finally {
      publishing.value = false
    }
  }

  const resetting = ref(false)

  async function resetDraft() {
    // Cancel pending debounced save so a stale PATCH can't clobber the reset
    if (_saveTimer) {
      clearTimeout(_saveTimer)
      _saveTimer = null
    }
    _pendingFields = {}
    // Invalidate any PATCH already in flight — its response will be dropped
    _opToken += 1

    resetting.value = true
    saveError.value = null
    try {
      const reverted = await fetchWithRefresh<AgentProfileData>('/api/agent-profile/reset', {
        method: 'POST',
      })
      profile.value = reverted
      changedSections.value = new Set()
    } catch (e: any) {
      saveError.value = e?.data?.detail ?? e.message
    } finally {
      resetting.value = false
    }
  }

  async function uploadAvatar(file: File) {
    const form = new FormData()
    form.append('file', file)
    try {
      const result = await fetchWithRefresh<{ avatar_url: string }>('/api/agent-profile/avatar', {
        method: 'POST',
        body: form,
      })
      if (profile.value) {
        profile.value.avatar_url = result.avatar_url
        changedSections.value = new Set([...changedSections.value, 'identity'])
      }
    } catch (e: any) {
      saveError.value = e?.data?.detail ?? e.message
    }
  }

  const isDraft = computed(() =>
    profile.value !== null &&
    (profile.value.published_version === null ||
     profile.value.version !== profile.value.published_version)
  )

  const changedCount = computed(() => changedSections.value.size)

  const versionLabel = computed(() => {
    if (!profile.value) return ''
    return `v${profile.value.version}`
  })

  const lastPublishedLabel = computed(() => {
    if (!profile.value?.published_at) return 'never published'
    const d = new Date(profile.value.published_at)
    const diffDays = Math.floor((Date.now() - d.getTime()) / 86_400_000)
    if (diffDays === 0) return 'published today'
    if (diffDays === 1) return 'published yesterday'
    return `last published ${diffDays}d ago`
  })

  return {
    profile, models, loading, saving, publishing, resetting, saveError,
    isDraft, changedCount, changedSections, versionLabel, lastPublishedLabel,
    fetchProfile, fetchModels, updateField, publish, resetDraft, uploadAvatar,
  }
}
