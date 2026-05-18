import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

// ── Stub auto-imports ────────────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.mock('lucide-vue-next', () => ({ Sparkles: { render: () => null, setup: () => null } }))

const mockFetch = vi.fn()
vi.stubGlobal('useApi', () => ({ fetchWithRefresh: mockFetch }))

const mockNavigate = vi.fn()
vi.stubGlobal('navigateTo', mockNavigate)

const mockRefreshBriefings = vi.fn()
vi.stubGlobal('useBriefingsList', () => ({ refresh: mockRefreshBriefings }))

import BriefMeButton from '~/components/dashboard/BriefMeButton.vue'

async function clickButton() {
  const btn = document.querySelector('button')
  if (btn) btn.click()
}

describe('BriefMeButton', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    mockNavigate.mockReset()
    mockRefreshBriefings.mockReset()
  })

  it('renders "Brief me" label when idle', () => {
    mount(BriefMeButton, { props: { dashboardId: 1 }, attachTo: document.body })
    const btn = document.querySelector('button')!
    expect(btn.textContent).toMatch(/Brief me/i)
    document.body.innerHTML = ''
  })

  it('POSTs, refreshes the briefings list, then navigates', async () => {
    mockFetch.mockResolvedValue({ briefing_id: 7, status: 'generating' })
    mount(BriefMeButton, { props: { dashboardId: 1 }, attachTo: document.body })

    await clickButton()
    await new Promise(r => setTimeout(r, 10))

    expect(mockFetch).toHaveBeenCalledWith('/api/dashboards/1/brief', { method: 'POST' })
    expect(mockRefreshBriefings).toHaveBeenCalledTimes(1)
    expect(mockNavigate).toHaveBeenCalledWith('/chat?briefing=7')
    document.body.innerHTML = ''
  })

  it('does not refresh or navigate when POST fails', async () => {
    const onRejection = vi.fn()
    process.on('unhandledRejection', onRejection)

    mockFetch.mockRejectedValue(new Error('Network down'))
    mount(BriefMeButton, { props: { dashboardId: 1 }, attachTo: document.body })

    await clickButton()
    await new Promise(r => setTimeout(r, 50))

    process.off('unhandledRejection', onRejection)

    expect(mockRefreshBriefings).not.toHaveBeenCalled()
    expect(mockNavigate).not.toHaveBeenCalled()
    const btn = document.querySelector('button')! as HTMLButtonElement
    expect(btn.disabled).toBe(false)
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

  it('uses the correct dashboardId prop', async () => {
    mockFetch.mockResolvedValue({ briefing_id: 99, status: 'generating' })
    mount(BriefMeButton, { props: { dashboardId: 42 }, attachTo: document.body })

    await clickButton()
    await new Promise(r => setTimeout(r, 10))

    expect(mockFetch).toHaveBeenCalledWith('/api/dashboards/42/brief', { method: 'POST' })
    expect(mockRefreshBriefings).toHaveBeenCalled()
    expect(mockNavigate).toHaveBeenCalledWith('/chat?briefing=99')
    document.body.innerHTML = ''
  })
})
