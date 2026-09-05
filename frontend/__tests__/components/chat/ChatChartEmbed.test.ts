import { describe, it, expect, vi } from 'vitest'
import { mount, shallowMount } from '@vue/test-utils'
import { ref, computed } from 'vue'

// An ad-hoc chat chart is a FROZEN snapshot: the rows were queried once, server
// side, and the message was persisted with them. Re-running the query later
// would silently rewrite a historical answer — so neither the filter watcher nor
// a manual Refresh click may fire. autoRefresh=false used to disable only the
// watcher; DashboardWidget still rendered its Refresh control.

const mockRefresh = vi.fn()
vi.mock('~/composables/useWidgetData', () => ({
  useWidgetData: (_w: any, autoRefresh = true) => {
    if (autoRefresh) mockRefresh()
    return {
      loading: ref(false),
      error: ref(null),
      lastRefreshedAt: ref(null),
      hasDataSource: computed(() => true),
      refresh: mockRefresh,
    }
  },
}))
vi.mock('~/composables/useConnections', () => ({
  useConnections: () => ({ ensureLoaded: vi.fn(), getSourceLabel: () => '' }),
}))

import ChatChartEmbed from '~/components/chat/ChatChartEmbed.vue'
import DashboardWidget from '~/components/dashboard/DashboardWidget.vue'

const DashboardWidgetStub = {
  name: 'DashboardWidget',
  props: ['widget', 'autoRefresh', 'editMode', 'dashboardId'],
  template: '<div />',
}

const snapshotWidget = () => ({
  id: 'w1',
  position: { x: 0, y: 0, w: 6, h: 4 },
  widget: { type: 'chart', config: { type: 'bar', title: 'Sales', labels: ['a'], datasets: [] } },
  dataSource: { connectionId: 1, sql: 'select 1', mapping: {} },
})

const chartRef = () => ({ kind: 'adhoc' as const, widget: snapshotWidget(), connection_id: 1 })

describe('ChatChartEmbed', () => {
  it('renders the snapshot with refresh disabled and in read-only mode', () => {
    const wrapper = mount(ChatChartEmbed, {
      props: { chartRef: chartRef() },
      global: { stubs: { DashboardWidget: DashboardWidgetStub } },
    })
    const widget = wrapper.findComponent(DashboardWidgetStub)
    expect(widget.props('autoRefresh')).toBe(false)
    // editMode is a required prop with no default — omitting it leaves the
    // widget in undefined-mode and warns on every chat message.
    expect(widget.props('editMode')).toBe(false)
  })

  it('sizes the wrapper from the widget height so flex-height charts do not collapse', () => {
    const wrapper = mount(ChatChartEmbed, {
      props: { chartRef: chartRef() },
      global: { stubs: { DashboardWidget: DashboardWidgetStub } },
    })
    expect(wrapper.attributes('style')).toContain('height: 280px')  // 4 rows * 70px
  })
})

describe('DashboardWidget refresh controls', () => {
  const mountWidget = (autoRefresh: boolean) =>
    shallowMount(DashboardWidget, {
      props: { widget: snapshotWidget() as any, editMode: false, autoRefresh },
    })

  it('offers no refresh control for a frozen snapshot', () => {
    const wrapper = mountWidget(false)
    expect(wrapper.find('.refresh-float').exists()).toBe(false)
    expect(wrapper.find('button[title="Refresh data"]').exists()).toBe(false)
  })

  it('still offers refresh for a live dashboard widget', () => {
    const wrapper = mountWidget(true)
    expect(wrapper.find('.refresh-float').exists()).toBe(true)
  })

  it('never fires a request for a frozen snapshot', async () => {
    mockRefresh.mockClear()
    mountWidget(false)
    await Promise.resolve()
    expect(mockRefresh).not.toHaveBeenCalled()
  })
})
