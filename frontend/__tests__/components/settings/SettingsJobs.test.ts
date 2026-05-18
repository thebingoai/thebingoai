import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed, reactive } from 'vue'

// ── Stub Nuxt auto-imports ───────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('reactive', reactive)
vi.stubGlobal('onMounted', (cb: any) => cb())

// ── Stub lucide icons used by SettingsJobs ───────────────────────────
vi.mock('lucide-vue-next', () => {
  const stub = { render: () => null, setup: () => null }
  return {
    Timer: stub, Pencil: stub, History: stub, Play: stub,
    Trash2: stub, ChevronDown: stub, LayoutDashboard: stub,
  }
})

// ── Stub vue-sonner toast ────────────────────────────────────────────
vi.mock('vue-sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }))

// ── Stub useApi: minimal endpoints used by mount-time fetchJobs() ────
const heartbeatJobs = [
  {
    id: 'job-chat-1',
    name: 'Daily standup summary',
    prompt: 'Summarize recent activity',
    schedule_type: 'preset',
    schedule_value: 'daily',
    cron_expression: '0 9 * * *',
    is_active: true,
    kind: 'chat',
    next_run_at: '2026-05-18T09:00:00Z',
    last_run_at: null,
    created_at: '2026-05-17T00:00:00Z',
    updated_at: '2026-05-17T00:00:00Z',
  },
  {
    id: 'job-brief-1',
    name: 'Dashboard Analysis: Test Dashboard',
    prompt: 'analyze dashboard 1',
    schedule_type: 'preset',
    schedule_value: 'daily',
    cron_expression: '0 9 * * *',
    is_active: true,
    kind: 'briefing',
    next_run_at: '2026-05-18T09:00:00Z',
    last_run_at: null,
    created_at: '2026-05-17T01:00:00Z',
    updated_at: '2026-05-17T01:00:00Z',
  },
]

vi.stubGlobal('useApi', () => ({
  heartbeatJobs: {
    list: vi.fn().mockResolvedValue(heartbeatJobs),
  },
  dashboards: { triggerRefresh: vi.fn(), listRefreshRuns: vi.fn() },
}))

// ── Stub dashboard store (Pinia) — imported directly, mock the module ─
vi.mock('~/stores/dashboard', () => ({
  useDashboardStore: () => ({
    dashboards: [],
    fetchDashboards: vi.fn().mockResolvedValue(undefined),
    setSchedule: vi.fn(),
    toggleSchedule: vi.fn(),
    removeSchedule: vi.fn(),
  }),
}))

// ── Stub util format ─────────────────────────────────────────────────
vi.mock('~/utils/format', () => ({ parseUtcDate: (s: string) => new Date(s) }))

// ── Stub Ui + ScheduleEditor as inert containers ─────────────────────
const inert = (name: string) => ({ name, template: `<div class="${name}-stub"><slot/><slot name="footer"/></div>` })
const globalStubs = {
  UiButton: inert('UiButton'),
  UiDialog: inert('UiDialog'),
  UiSkeleton: inert('UiSkeleton'),
  UiEmptyState: inert('UiEmptyState'),
  ScheduleEditor: inert('ScheduleEditor'),
}

import SettingsJobs from '~/components/settings/SettingsJobs.vue'

async function flush() {
  await new Promise(r => setTimeout(r, 0))
  await new Promise(r => setTimeout(r, 0))
}

describe('SettingsJobs — kind badges + conditional pencil', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('renders both rows with kind-specific badges', async () => {
    const w = mount(SettingsJobs, { global: { stubs: globalStubs }, attachTo: document.body })
    await flush()
    const text = w.text()
    expect(text).toContain('Daily standup summary')
    expect(text).toContain('Dashboard Analysis: Test Dashboard')
    expect(text).toContain('Job')
    expect(text).toContain('Briefing')
  })

  it('hides "Edit name & prompt" button on briefing-kind row', async () => {
    const w = mount(SettingsJobs, { global: { stubs: globalStubs }, attachTo: document.body })
    await flush()
    // Only one Edit button total — the briefing row must have it hidden
    const editBtns = w.findAll('button[title="Edit name & prompt"]')
    expect(editBtns).toHaveLength(1)
    // Locate each row container by its job name and assert presence/absence
    const rows = w.findAll('div.rounded-lg.border')
    const chatRow = rows.find(r => r.text().includes('Daily standup summary'))!
    const briefingRow = rows.find(r => r.text().includes('Dashboard Analysis'))!
    expect(chatRow.find('button[title="Edit name & prompt"]').exists()).toBe(true)
    expect(briefingRow.find('button[title="Edit name & prompt"]').exists()).toBe(false)
  })

  it('keeps schedule chip, history, trigger, and delete on both rows', async () => {
    const w = mount(SettingsJobs, { global: { stubs: globalStubs }, attachTo: document.body })
    await flush()
    expect(w.findAll('button[title="View run history"]')).toHaveLength(2)
    expect(w.findAll('button[title="Trigger now"]')).toHaveLength(2)
    expect(w.findAll('button[title="Delete job"]')).toHaveLength(2)
  })
})
