import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, onMounted, toRaw } from 'vue'

// BriefingWidgetEmbed fetches the (data-less) widget shell on mount, then either
// merges a generation-time snapshot (no SQL) or — for pre-rollout briefings —
// falls back to a live refresh. @loaded must always fire so the PDF wait clears.

vi.stubGlobal('ref', ref)
vi.stubGlobal('onMounted', onMounted)
vi.stubGlobal('toRaw', toRaw)

const mockFetch = vi.fn()
vi.stubGlobal('useApi', () => ({ fetchWithRefresh: mockFetch }))

const mockRefresh = vi.fn()
const mockUseWidgetData = vi.fn(() => ({ refresh: mockRefresh }))
vi.stubGlobal('useWidgetData', mockUseWidgetData)

import BriefingWidgetEmbed from '~/components/briefings/BriefingWidgetEmbed.vue'

// Named stub (rather than `stubs: { DashboardWidget: true }`) so we can read
// back the props actually passed to it — an anonymous `true` auto-stub loses
// that in this Nuxt-auto-import setup.
const DashboardWidgetStub = {
  name: 'DashboardWidget',
  props: ['widget', 'autoRefresh', 'editMode', 'dashboardId'],
  template: '<div />',
}

// onMounted awaits a dynamic import('~/utils/widgetMerge'); a couple flushes
// aren't enough to settle it. Tick microtasks until emitted('loaded') fires.
// Bounded by a deadline rather than a tick count — how many ticks that import
// needs depends on how loaded the run is, and a fixed count loses under a full
// parallel suite.
async function settle(wrapper: any) {
  const deadline = Date.now() + 2000
  while (!wrapper.emitted('loaded') && Date.now() < deadline) {
    await flushPromises()
    await new Promise((r) => setTimeout(r))
  }
}

const shell = () => ({
  id: 'w1',
  widget: { type: 'bar', config: { type: 'bar' } },
  dataSource: { connectionId: 1, sql: 'select 1', mapping: {} },
})

const mountEmbed = (props: Record<string, any>) =>
  mount(BriefingWidgetEmbed, {
    props: { widgetId: 'w1', dashboardId: 10, ...props },
    global: { stubs: { DashboardWidget: true } },
  })

describe('BriefingWidgetEmbed', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    mockRefresh.mockReset()
    mockUseWidgetData.mockClear()
  })

  it('merges the snapshot and skips the live refresh when a snapshot is present', async () => {
    mockFetch.mockResolvedValue(shell())
    const wrapper = mountEmbed({ snapshot: { series: [1, 2, 3] } })
    await settle(wrapper)

    expect(mockRefresh).not.toHaveBeenCalled()
    expect((wrapper.vm as any).widget.widget.config.series).toEqual([1, 2, 3])
    expect(wrapper.emitted('loaded')).toHaveLength(1)
  })

  it('falls back to a live refresh when no snapshot is given', async () => {
    mockFetch.mockResolvedValue(shell())
    const wrapper = mountEmbed({})
    await settle(wrapper)

    expect(mockRefresh).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('loaded')).toHaveLength(1)
  })

  it('still emits loaded when the widget fetch fails (deleted widget)', async () => {
    mockFetch.mockRejectedValue(new Error('404'))
    const wrapper = mountEmbed({ snapshot: { series: [1] } })
    await settle(wrapper)

    expect(mockRefresh).not.toHaveBeenCalled()
    expect((wrapper.vm as any).widget).toBeNull()
    expect(wrapper.emitted('loaded')).toHaveLength(1)
  })

  it('skips the authed widget fetch when a widget is passed inline', async () => {
    const wrapper = mountEmbed({
      // Backend-stripped shape: no dataSource, so refresh() cannot fire either.
      widget: { id: 'w1', widget: { type: 'bar', config: { type: 'bar' } } },
      snapshot: { series: [1, 2, 3] },
    })
    await settle(wrapper)

    // The whole point: an anonymous visitor has no token for this endpoint.
    expect(mockFetch).not.toHaveBeenCalled()
    expect(mockRefresh).not.toHaveBeenCalled()
    expect((wrapper.vm as any).widget.widget.config.series).toEqual([1, 2, 3])
    expect(wrapper.emitted('loaded')).toHaveLength(1)
  })

  it('does not mutate the inline widget prop when merging the snapshot', async () => {
    const inline = { id: 'w1', widget: { type: 'bar', config: { type: 'bar' } } }
    const wrapper = mountEmbed({ widget: inline, snapshot: { series: [9] } })
    await settle(wrapper)

    // mergeRefreshedConfig Object.assigns into widget.widget.config — a shallow
    // copy would write straight through into the caller's object.
    expect((inline.widget.config as any).series).toBeUndefined()
  })

  it('always passes editMode=false to DashboardWidget — briefing embeds are read-only, not accidentally-falsy-undefined', async () => {
    mockFetch.mockResolvedValue(shell())
    const wrapper = mount(BriefingWidgetEmbed, {
      props: { widgetId: 'w1', dashboardId: 10, snapshot: { series: [1, 2, 3] } },
      global: { stubs: { DashboardWidget: DashboardWidgetStub } },
    })
    await settle(wrapper)

    const dashboardWidget = wrapper.findComponent(DashboardWidgetStub)
    expect(dashboardWidget.exists()).toBe(true)
    expect(dashboardWidget.props('editMode')).toBe(false)
  })

  it('never falls back to the authed fetch when both widget and dashboardId are missing (public share view, widget dropped from the frozen snapshot)', async () => {
    const wrapper = mountEmbed({ widget: undefined, dashboardId: undefined })
    await settle(wrapper)

    // An anonymous visitor has no token for the authed endpoint. Hitting it
    // would 401 -> refreshAccessToken() -> logout() + redirect to /login,
    // dumping the visitor off the public share page.
    expect(mockFetch).not.toHaveBeenCalled()
    expect((wrapper.vm as any).widget).toBeNull()
    expect(wrapper.emitted('loaded')).toHaveLength(1)
    expect(wrapper.find('div').exists()).toBe(false)
  })

  it('renders nothing (and does not throw) when a snapshot is present but the widget shape is missing', async () => {
    // Backend serves widget_snapshots unfiltered, so a widget deleted from the
    // dashboard before share time arrives as snapshot-without-widget. The old
    // code Object.assigned into a null widget, relying on the catch to swallow
    // the TypeError — same blank render, but by accident.
    const wrapper = mountEmbed({ widget: undefined, dashboardId: undefined, snapshot: { series: [1] } })
    await settle(wrapper)

    expect(mockFetch).not.toHaveBeenCalled()
    expect(mockRefresh).not.toHaveBeenCalled()
    expect((wrapper.vm as any).widget).toBeNull()
    expect(wrapper.emitted('loaded')).toHaveLength(1)
    expect(wrapper.find('div').exists()).toBe(false)
  })

  it('scopes the refresh to its OWN dashboard, not whichever the store is on', async () => {
    // On /chat and /briefings the dashboard store is reset, so a refresh that
    // derives dashboard_id from it drops the id entirely — the backend then
    // loses that dashboard's DataPlane / cache / serving-org path.
    mockFetch.mockResolvedValue(shell())
    const wrapper = mount(BriefingWidgetEmbed, {
      props: { widgetId: 'w1', dashboardId: 10 },
      global: { stubs: { DashboardWidget: DashboardWidgetStub } },
    })
    await settle(wrapper)

    expect(mockUseWidgetData).toHaveBeenCalledWith(
      expect.anything(), true, { dashboardId: 10 },
    )
    expect(wrapper.findComponent(DashboardWidgetStub).props('dashboardId')).toBe(10)
  })
})
