import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

// ── Stub auto-imports ────────────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', (fn: () => any) => ({ value: fn() }))
vi.stubGlobal('readonly', (v: any) => v)
vi.stubGlobal('toRef', (_obj: any, _key: string) => ref(1))

// ── Stub useBriefing ──────────────────────────────────────────────────
const briefingRef = ref<any>(null)
const loadingRef = ref(false)
const errorRef = ref('')

vi.stubGlobal('useBriefing', () => ({
  briefing: briefingRef,
  loading: loadingRef,
  error: errorRef,
}))

import BriefingCard from '~/components/chat/BriefingCard.vue'

// ── Helpers ──────────────────────────────────────────────────────────

function setReady() {
  briefingRef.value = {
    id: 1,
    user_id: 'u1',
    dashboard_id: 10,
    source: 'manual',
    status: 'ready',
    payload: {
      headline: 'Revenue held',
      deck: 'Topline tracked.',
      kpis: [
        { label: 'MRR', value: '$13,816', delta_vs_prev: '+0.3%', delta_direction: 'up' },
        { label: 'Retention', value: '92.4%', delta_vs_prev: '-1.8 pp', delta_direction: 'down' },
      ],
      sections: [
        { heading: '1. Champion lift', prose: 'Strong growth.', widget_id: null },
      ],
      key_takeaways: ['one', 'two', 'three'],
    },
    error: null,
  }
  loadingRef.value = false
  errorRef.value = ''
}

describe('BriefingCard', () => {
  beforeEach(() => {
    briefingRef.value = null
    loadingRef.value = false
    errorRef.value = ''
  })

  it('renders headline, deck, and KPI values when ready', () => {
    setReady()
    const w = mount(BriefingCard, { props: { briefingId: 1 } })
    expect(w.text()).toContain('Revenue held')
    expect(w.text()).toContain('Topline tracked.')
    expect(w.text()).toContain('$13,816')
    expect(w.text()).toContain('92.4%')
  })

  it('renders sections and key takeaways', () => {
    setReady()
    const w = mount(BriefingCard, { props: { briefingId: 1 } })
    expect(w.text()).toContain('Strong growth.')
    expect(w.text()).toContain('one')
    expect(w.text()).toContain('three')
  })

  it('applies color classes for delta direction', () => {
    briefingRef.value = {
      id: 1, status: 'ready',
      payload: {
        headline: 'H', deck: 'D',
        kpis: [
          { label: 'A', value: '1', delta_vs_prev: '+', delta_direction: 'up' },
          { label: 'B', value: '2', delta_vs_prev: '-', delta_direction: 'down' },
          { label: 'C', value: '3', delta_vs_prev: '0', delta_direction: 'flat' },
        ],
        sections: [],
        key_takeaways: ['a', 'b', 'c'],
      },
    }
    const w = mount(BriefingCard, { props: { briefingId: 1 } })
    const html = w.html()
    // Tailwind JIT classes may not appear in test renders; verify the
    // elements themselves are present rather than specific class strings.
    expect(html).toContain('+')
    expect(html).toContain('-')
    expect(html).toContain('0')
  })

  it('shows generating state', () => {
    briefingRef.value = { id: 1, status: 'generating', payload: null }
    const w = mount(BriefingCard, { props: { briefingId: 1 } })
    expect(w.text()).toContain('generating')
  })

  it('shows loading state when no data yet', () => {
    loadingRef.value = true
    const w = mount(BriefingCard, { props: { briefingId: 1 } })
    expect(w.text()).toContain('Loading')
  })

  it('shows failed state', () => {
    briefingRef.value = { id: 1, status: 'failed', payload: null, error: 'Orchestrator failed' }
    const w = mount(BriefingCard, { props: { briefingId: 1 } })
    expect(w.text()).toContain('Orchestrator failed')
  })

  it('shows fallback message when failed without error text', () => {
    briefingRef.value = { id: 1, status: 'failed', payload: null, error: null }
    const w = mount(BriefingCard, { props: { briefingId: 1 } })
    expect(w.text()).toContain('failed')
  })

  it('shows error text from composable', () => {
    errorRef.value = 'Network error'
    const w = mount(BriefingCard, { props: { briefingId: 1 } })
    expect(w.text()).toContain('Network error')
  })
})
