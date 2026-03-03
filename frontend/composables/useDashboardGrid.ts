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
  let grid: GridStack | null = null

  // Maps widgetId → the .grid-stack-item-content element (Teleport target)
  const contentRefs = reactive(new Map<string, HTMLElement>())

  function initGrid() {
    const el = containerRef.value
    if (!el || grid) return

    grid = GridStack.init(
      {
        column: 12,
        cellHeight: 70,
        margin: 4,
        animate: true,
        float: false,
        staticGrid: !store.editMode,
        resizable: { handles: 'se' },
        draggable: { handle: '.widget-drag-handle' },
      },
      el,
    )

    // Sync positions back to store after drag/resize
    grid.on('change', (_event: Event, nodes: GridStackNode[]) => {
      if (!nodes) return
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

    // Build .grid-stack-item with gs-* data attributes so makeWidget can read them
    const item = document.createElement('div')
    item.classList.add('grid-stack-item')
    item.dataset.widgetId = widget.id
    item.setAttribute('gs-x', String(x))
    item.setAttribute('gs-y', String(y))
    item.setAttribute('gs-w', String(w))
    item.setAttribute('gs-h', String(h))
    if (minW) item.setAttribute('gs-min-w', String(minW))
    if (minH) item.setAttribute('gs-min-h', String(minH))
    item.setAttribute('gs-id', widget.id)

    const content = document.createElement('div')
    content.classList.add('grid-stack-item-content')
    item.appendChild(content)

    // Append to grid container then register with GridStack
    grid.el.appendChild(item)
    grid.makeWidget(item)

    contentRefs.set(widget.id, content)
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

  // Initial setup
  onMounted(() => {
    initGrid()
    for (const widget of widgets.value) {
      addWidgetToGrid(widget)
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
        if (widget) addWidgetToGrid(widget)
      }
    },
  )

  // Watch edit mode
  watch(
    () => store.editMode,
    (isEdit) => syncStaticMode(!isEdit),
  )

  onBeforeUnmount(() => {
    grid?.destroy(false)
    grid = null
    contentRefs.clear()
  })

  return { contentRefs }
}
