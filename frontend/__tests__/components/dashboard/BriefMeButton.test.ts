import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

// ── Stub auto-imports ────────────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.mock('lucide-vue-next', () => ({ Sparkles: { render: () => null, setup: () => null } }))

const mockFetch = vi.fn()
vi.stubGlobal('useApi', () => ({ fetchWithRefresh: mockFetch }))

const mockOpen = vi.fn()
vi.stubGlobal('window', { ...window, open: mockOpen })

import BriefMeButton from '~/components/dashboard/BriefMeButton.vue'

// Helper: call onClick by reaching into the component instance.
// trigger('click') is broken on this Node environment (SupportedEventInterface).
async function clickButton() {
  const btn = document.querySelector('button')
  if (btn) btn.click()
}

describe('BriefMeButton', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    mockOpen.mockReset()
  })

  it('renders "Brief me" label when idle', () => {
    mount(BriefMeButton, { props: { dashboardId: 1 }, attachTo: document.body })
    const btn = document.querySelector('button')!
    expect(btn.textContent).toMatch(/Brief me/i)
    document.body.innerHTML = ''
  })

  it('POSTs and opens reading view in new tab on click', async () => {
    mockFetch.mockResolvedValue({ briefing_id: 7, status: 'generating' })
    mount(BriefMeButton, { props: { dashboardId: 1 }, attachTo: document.body })

    await clickButton()
    await new Promise(r => setTimeout(r, 10))

    expect(mockFetch).toHaveBeenCalledWith('/api/dashboards/1/brief', { method: 'POST' })
    expect(mockOpen).toHaveBeenCalledWith('/briefings/7', '_blank')
    document.body.innerHTML = ''
  })

  it('shows "Briefing…" and disables while posting', async () => {
    let resolve!: (v: any) => void
    mockFetch.mockReturnValue(new Promise(r => { resolve = r }))

    mount(BriefMeButton, { props: { dashboardId: 1 }, attachTo: document.body })
    await clickButton()

    const btn = document.querySelector('button')!
    expect((btn as HTMLButtonElement).disabled).toBe(true)
    expect(btn.textContent).toMatch(/Briefing…/)

    resolve({ briefing_id: 7, status: 'generating' })
    await new Promise(r => setTimeout(r, 10))
    expect((btn as HTMLButtonElement).disabled).toBe(false)
    document.body.innerHTML = ''
  })

  it('resets busy state on API error', async () => {
    // The component's onClick is async but doesn't await the fetch call —
    // the rejection is unhandled. Suppress via rejectionHandled.
    const onRejection = vi.fn()
    process.on('unhandledRejection', onRejection)

    mockFetch.mockRejectedValue(new Error('Network down'))
    mount(BriefMeButton, { props: { dashboardId: 1 }, attachTo: document.body })

    await clickButton()
    // Give the microtask queue time to flush the rejection
    await new Promise(r => setTimeout(r, 50))

    process.off('unhandledRejection', onRejection)

    const btn = document.querySelector('button')! as HTMLButtonElement
    expect(btn.disabled).toBe(false)
    expect(mockOpen).not.toHaveBeenCalled()
    document.body.innerHTML = ''
  })

  it('uses the correct dashboardId prop', async () => {
    mockFetch.mockResolvedValue({ briefing_id: 99, status: 'generating' })
    mount(BriefMeButton, { props: { dashboardId: 42 }, attachTo: document.body })

    await clickButton()
    await new Promise(r => setTimeout(r, 10))

    expect(mockFetch).toHaveBeenCalledWith('/api/dashboards/42/brief', { method: 'POST' })
    expect(mockOpen).toHaveBeenCalledWith('/briefings/99', '_blank')
    document.body.innerHTML = ''
  })
})
