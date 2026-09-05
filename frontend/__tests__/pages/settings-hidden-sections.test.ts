import { describe, it, expect, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { ref, computed, watch, reactive } from 'vue'

// ── Nuxt auto-import stubs ──────────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)
vi.stubGlobal('onMounted', vi.fn())          // skip loadCounts' API calls
vi.stubGlobal('definePageMeta', vi.fn())
vi.stubGlobal('useIsMobile', () => ({ isMobile: ref(false) }))
vi.stubGlobal('useFeatureConfig', () => ({ config: ref({ telegram_enabled: true, credits_enabled: true }) }))
vi.stubGlobal('useWorkspaceStore', () => ({ isViewer: false }))
vi.stubGlobal('useSettingsTabs', () => ({ list: () => [] }))
vi.stubGlobal('useLazyFetch', () => ({ data: ref(null) }))
vi.stubGlobal('useApi', () => ({}))
vi.stubGlobal('useChannels', () => ({}))

const router = { replace: vi.fn(), push: vi.fn(), back: vi.fn() }
vi.stubGlobal('useRouter', () => router)

let route: { query: Record<string, string> }
vi.stubGlobal('useRoute', () => route)
let currentSection: ReturnType<typeof ref<string>>
vi.stubGlobal('useSettingsState', () => ({ currentSection }))

import SettingsPage from '~/pages/settings.vue'

const stubs = Object.fromEntries(
  ['Agent', 'Connections', 'Skills', 'Jobs', 'Memory', 'Profile', 'ApiKeys', 'Credits', 'Channels']
    .map(n => [`Settings${n}`, { name: `Settings${n}`, template: `<div data-section="${n.toLowerCase()}" />` }]),
)

function mountAt(tab: string | undefined, retained = 'connections') {
  route = reactive({ query: tab ? { tab } : {} })
  currentSection = ref(retained)
  return shallowMount(SettingsPage, { global: { stubs } })
}

describe('settings sections hidden from the nav stay routable', () => {
  it('lists neither Skills nor Memory in the nav', () => {
    const w = mountAt(undefined)
    const names = w.findAll('nav button').map(b => b.text())
    expect(names).toContain('Connections')
    expect(names).not.toContain('Skills')
    expect(names).not.toContain('Memory')
  })

  it('?tab=skills opens the Skills manager (the home screen CTA links here)', () => {
    const w = mountAt('skills')
    expect(currentSection.value).toBe('skills')
    expect(w.find('[data-section="skills"]').exists()).toBe(true)
  })

  it('?tab=memory opens the Memory controls, whatever section was open before', () => {
    const w = mountAt('memory', 'profile')
    expect(currentSection.value).toBe('memory')
    expect(w.find('[data-section="memory"]').exists()).toBe(true)
    expect(w.find('[data-section="profile"]').exists()).toBe(false)
  })
})
