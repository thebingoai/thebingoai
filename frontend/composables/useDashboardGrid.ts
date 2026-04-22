import { GridStack } from 'gridstack'
import type { GridStackNode } from 'gridstack'
import type { Ref } from 'vue'
import type { DashboardWidget, GridPosition } from '~/types/dashboard'
import { useDashboardStore } from '~/stores/dashboard'

export function useDashboardGrid(
  containerRef: Ref<HTMLElement | null>,
  widgets: Ref<DashboardWidget[]>,
) {
  const store = useDashboardStore()
  const { isMobile } = useIsMobile()
  let grid: GridStack | null = null

  // Maps widgetId → the .grid-stack-item-content element (Teleport target)
  const contentRefs = reactive(new Map<string, HTMLElement>())

  let desktopPositions: Array<{ id: string; pos: GridPosition }> | null = null
  let isColumnChanging = false

  function initGrid() {
    const el = containerRef.value
    if (!el || grid) return

    grid = GridStack.init(
      {
        column: isMobile.value ? 1 : 12,
        cellHeight: 70,
        margin: 4,
        animate: true,
        float: false,
        resizable: { handles: 'se' },
        draggable: { handle: '.widget-drag-handle' },
      },
      el,
    )

    // Explicitly set static state from current store value
    grid.setStatic(!store.editMode)

    // Sync positions back to store after drag/resize
    grid.on('change', (_event: Event, nodes: GridStackNode[]) => {
      if (!nodes || isColumnChanging) return
      for (const node of nodes) {
        const id = node.el?.dataset.widgetId
        if (!id) continue
        const pos: Partial<GridPosition> = {
          x: node.x ?? 0,
          y: node.y ?? 0,
          w: node.w ?? 1,
          h: node.h ?? 1,
        }
        store.updateWidgetPosition(id, pos)
      }
    })
  }

  function addWidgetToGrid(widget: DashboardWidget) {
    if (!grid) return

    const { x, y, w, h, minW, minH } = widget.position

    // Use addWidget with explicit options so GridStack handles DOM creation and
    // grid node registration in one call, correctly respecting position values
    const el = grid.addWidget({
      x, y, w, h,
      minW: minW || undefined,
      minH: minH || undefined,
      id: widget.id,
    })

    el.dataset.widgetId = widget.id
    const content = el.querySelector('.grid-stack-item-content') as HTMLElement
    if (content) {
      contentRefs.set(widget.id, content)
    }
  }

  function removeWidgetFromGrid(widgetId: string) {
    if (!grid) return
    const items = grid.getGridItems()
    const item = items.find(el => el.dataset.widgetId === widgetId)
    if (item) grid.removeWidget(item)
    contentRefs.delete(widgetId)
  }

  function syncStaticMode(isStatic: boolean) {
    grid?.setStatic(isStatic)
  }

  function resizeWidget(widgetId: string, h: number) {
    if (!grid) return
    const el = grid.getGridItems().find(el => el.dataset.widgetId === widgetId)
    if (el) grid.update(el, { h })
  }

  // Track which widgets have been staggered in (for skeleton → content transition)
  const renderedWidgets = ref(new Set<string>())

  // Initial setup — stagger widget additions across animation frames to avoid
  // blocking the main thread with simultaneous Chart.js/table rendering
  onMounted(async () => {
    initGrid()
    if (!grid || !widgets.value.length) return

    for (const widget of widgets.value) {
      try {
        grid.batchUpdate()
        addWidgetToGrid(widget)
        grid.batchUpdate(false)
      } catch (e) {
        console.warn(`[DashboardGrid] Failed to add widget ${widget.id}:`, e)
      }

      // Yield to the browser between widgets so each gets its own frame
      await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))

      renderedWidgets.value.add(widget.id)
    }
  })

  // Watch for new/removed widgets
  watch(
    () => widgets.value.map(w => w.id),
    (newIds, oldIds) => {
      if (!grid) return
      const added = newIds.filter(id => !oldIds.includes(id))
      const removed = oldIds.filter(id => !newIds.includes(id))

      for (const id of removed) removeWidgetFromGrid(id)

      for (const id of added) {
        const widget = widgets.value.find(w => w.id === id)
        if (widget) {
          addWidgetToGrid(widget)
          renderedWidgets.value.add(id)
        }
      }
    },
  )

  // Watch edit mode — immediate ensures correct state even if editMode was already true on mount
  watch(
    () => store.editMode,
    (isEdit) => syncStaticMode(!isEdit),
    { flush: 'post', immediate: true },
  )

  // Collapse to single column on mobile, restore desktop layout when switching back
  watch(isMobile, async (mobile) => {
    if (!grid) return

    if (mobile) {
      // Snapshot desktop positions before collapsing
      desktopPositions = grid.getGridItems()
        .filter(el => el.dataset.widgetId)
        .map(el => ({
          id: el.dataset.widgetId!,
          pos: {
            x: el.gridstackNode?.x ?? 0,
            y: el.gridstackNode?.y ?? 0,
            w: el.gridstackNode?.w ?? 1,
            h: el.gridstackNode?.h ?? 1,
          },
        }))
      isColumnChanging = true
      grid.column(1)
      await nextTick()
      isColumnChanging = false
    } else {
      isColumnChanging = true
      // 'none' prevents GridStack from auto-scaling mobile positions to desktop
      grid.column(12, 'none')
      // Restore saved desktop positions, or fall back to store positions
      const positions = desktopPositions
        ?? widgets.value.map(w => ({ id: w.id, pos: w.position }))
      grid.batchUpdate()
      for (const { id, pos } of positions) {
        const el = grid.getGridItems().find(el => el.dataset.widgetId === id)
        if (el) grid.update(el, { x: pos.x, y: pos.y, w: pos.w, h: pos.h })
      }
      grid.batchUpdate(false)
      await nextTick()
      isColumnChanging = false
    }
  })

  onBeforeUnmount(() => {
    grid?.destroy(false)
    grid = null
    contentRefs.clear()
  })

  return { contentRefs, renderedWidgets, resizeWidget }
}
