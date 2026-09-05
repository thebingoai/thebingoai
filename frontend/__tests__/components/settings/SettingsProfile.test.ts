import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed, reactive } from 'vue'

// ── Nuxt auto-imports the SFC calls bare — expose as globals ──────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)

// Held across a mount so tests can assert the ref value after clicks.
let fontPref: ReturnType<typeof ref<'sm' | 'md' | 'lg'>>
let themePref: ReturnType<typeof ref<'kraft' | 'cool' | 'ink'>>

vi.stubGlobal('useAppFontSize', () => ({ preference: fontPref, sizes: ['sm', 'md', 'lg'] }))
vi.stubGlobal('useAppTheme', () => ({ preference: themePref, themes: ['kraft', 'cool', 'ink'] }))
vi.stubGlobal('useColorMode', () => reactive({ value: 'light', preference: 'light' }))
vi.stubGlobal('useAuthStore', () => ({
  user: { email: 'a@b.co', name: 'Ann', roles: ['admin'], created_at: '2026-01-01T00:00:00Z' },
  logout: vi.fn(),
}))
vi.stubGlobal('useRouter', () => ({ push: vi.fn() }))
vi.stubGlobal('onMounted', (cb: any) => cb())

const workspaceStub = reactive({ isViewer: false })
vi.stubGlobal('useWorkspaceStore', () => workspaceStub)

const getSettingsMock = vi.fn()
const updateSettingsMock = vi.fn()
vi.stubGlobal('useApi', () => ({ memory: { getSettings: getSettingsMock, updateSettings: updateSettingsMock } }))

import SettingsProfile from '~/components/settings/SettingsProfile.vue'

const globalStubs = {
  UiCard: { template: `<div><slot/></div>` },
  UiButton: { template: `<button><slot/></button>` },
  NuxtLink: { props: ['to'], template: `<a :href="to"><slot/></a>` },
}

const flush = async () => { await new Promise(r => setTimeout(r, 0)); await new Promise(r => setTimeout(r, 0)) }

function mountView() {
  return mount(SettingsProfile, { global: { stubs: globalStubs } })
}

const fontBtn = (w: any, label: string) =>
  w.findAll('button').find((b: any) => b.text() === label)

beforeEach(() => {
  fontPref = ref('md')
  themePref = ref('kraft')
  vi.clearAllMocks()
  workspaceStub.isViewer = false
  getSettingsMock.mockResolvedValue({ memory_enabled: true })
})

describe('SettingsProfile — text size control', () => {
  it('renders a Small / Medium / Large option', () => {
    const w = mountView()
    expect(fontBtn(w, 'Small')).toBeTruthy()
    expect(fontBtn(w, 'Medium')).toBeTruthy()
    expect(fontBtn(w, 'Large')).toBeTruthy()
  })

  it('marks the current size (md) as active', () => {
    const w = mountView()
    expect(fontBtn(w, 'Medium').classes()).toContain('bg-gray-900')
    expect(fontBtn(w, 'Small').classes()).not.toContain('bg-gray-900')
    expect(fontBtn(w, 'Large').classes()).not.toContain('bg-gray-900')
  })

  it('selecting Large sets the preference and moves the active class', async () => {
    const w = mountView()
    await fontBtn(w, 'Large').trigger('click')
    expect(fontPref.value).toBe('lg')
    expect(fontBtn(w, 'Large').classes()).toContain('bg-gray-900')
    expect(fontBtn(w, 'Medium').classes()).not.toContain('bg-gray-900')
  })

  it('selecting back to Medium round-trips the preference', async () => {
    const w = mountView()
    await fontBtn(w, 'Large').trigger('click')
    await fontBtn(w, 'Medium').trigger('click')
    expect(fontPref.value).toBe('md')
    expect(fontBtn(w, 'Medium').classes()).toContain('bg-gray-900')
    expect(fontBtn(w, 'Large').classes()).not.toContain('bg-gray-900')
  })
})

describe('SettingsProfile — theme switcher', () => {
  // Theme swatches carry no text; find them by their title attribute.
  const swatch = (w: any, theme: string) =>
    w.findAll('button').find((b: any) => b.attributes('title') === theme)

  it('renders a swatch per theme with the current one (kraft) active', () => {
    const w = mountView()
    expect(swatch(w, 'kraft').classes()).toContain('scale-110')
    expect(swatch(w, 'cool').classes()).not.toContain('scale-110')
    expect(swatch(w, 'ink').classes()).not.toContain('scale-110')
  })

  it('selecting a theme sets the preference and moves the active class', async () => {
    const w = mountView()
    await swatch(w, 'cool').trigger('click')
    expect(themePref.value).toBe('cool')
    expect(swatch(w, 'cool').classes()).toContain('scale-110')
    expect(swatch(w, 'kraft').classes()).not.toContain('scale-110')
  })
})

describe('SettingsProfile — auto-memory opt-out', () => {
  // The Memory section is hidden from the settings nav, so this switch is the
  // visible way to turn the default-on daily memory task off.
  const memToggle = (w: any) =>
    w.findAll('button').find((b: any) => /auto-memory/.test(b.attributes('title') || ''))

  it('shows the stored setting and links to the routable Memory page', async () => {
    getSettingsMock.mockResolvedValue({ memory_enabled: false })
    const w = mountView()
    await flush()
    expect(memToggle(w).attributes('title')).toBe('Enable auto-memory')
    expect(w.find('a[href="/settings?tab=memory"]').exists()).toBe(true)
  })

  it('flipping the switch persists the opposite value', async () => {
    updateSettingsMock.mockResolvedValue({ memory_enabled: false })
    const w = mountView()
    await flush()
    expect(memToggle(w).attributes('title')).toBe('Disable auto-memory')
    await memToggle(w).trigger('click')
    await flush()
    expect(updateSettingsMock).toHaveBeenCalledWith(false)
    expect(memToggle(w).attributes('title')).toBe('Enable auto-memory')
  })

  it('stays disabled until the stored value has loaded, so a late GET cannot undo a save', async () => {
    let settle!: (v: any) => void
    getSettingsMock.mockReturnValue(new Promise(r => { settle = r }))
    const w = mountView()
    await flush()
    expect(memToggle(w).attributes('disabled')).toBeDefined()
    await memToggle(w).trigger('click')
    expect(updateSettingsMock).not.toHaveBeenCalled()
    settle({ memory_enabled: false })
    await flush()
    expect(memToggle(w).attributes('disabled')).toBeUndefined()
    expect(memToggle(w).attributes('title')).toBe('Enable auto-memory')
  })

  it('hides the Manage link for viewers, whose settings nav has no Memory section', async () => {
    workspaceStub.isViewer = true
    const w = mountView()
    await flush()
    expect(memToggle(w)).toBeTruthy()
    expect(w.find('a[href="/settings?tab=memory"]').exists()).toBe(false)
  })
})
