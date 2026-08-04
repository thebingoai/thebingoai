import type { Ref } from 'vue'
import type { DashboardWidget, SectionColor, SectionWidgetConfig, TextWidgetConfig } from '~/types/dashboard'
import { isSectionHeader, sectionColorToken } from '~/types/dashboard'

export interface DashboardSection {
  id: string          // header widget id — stable scroll/jump target
  title: string
  color: SectionColor
  kind: 'section' | 'text'  // dedicated section widget vs legacy heading text widget
}

export interface SectionBounds {
  top: number         // px, relative to the grid wrapper
  height: number
}

/** First content line without markdown heading markers. */
export function sectionTitle(content: string): string {
  return (content ?? '').trimStart().split('\n')[0].replace(/^#+\s*/, '').trim()
}

/**
 * Derives dashboard sections from the flat widget list (a section = a
 * section-header text widget + every widget below it until the next header)
 * and measures each section's pixel bounding box from the gridstack item DOM.
 * Purely a visual layer — the grid and the persisted JSON stay flat.
 */
export function useDashboardSections(
  widgets: Ref<DashboardWidget[]>,
  wrapperRef: Ref<HTMLElement | null>,
) {
  const readingOrder = computed(() =>
    [...widgets.value].sort((a, b) => (a.position.y - b.position.y) || (a.position.x - b.position.x)),
  )

  const sections = computed<DashboardSection[]>(() =>
    readingOrder.value.filter(isSectionHeader).map((w) => {
      if (w.widget.type === 'section') {
        const config = w.widget.config as SectionWidgetConfig
        return { id: w.id, title: (config.title ?? '').trim(), color: sectionColorToken(config.sectionColor), kind: 'section' as const }
      }
      const config = w.widget.config as TextWidgetConfig
      return {
        id: w.id,
        title: sectionTitle(config.content),
        color: sectionColorToken(config.sectionColor),
        kind: 'text' as const,
      }
    }),
  )

  const bounds = ref<Record<string, SectionBounds>>({})

  // Adjacent gridstack items are contiguous (the 4px card breathing lives
  // inside each item), so all section spacing is carved out of the header
  // item's headroom above the bar (.section-widget-bar margin-top: 22px →
  // bar top = item + 26). Every band-to-content gap is 8px: band top starts
  // 8px above the bar, and the tails add 4px to the card's own 4px inset.
  // That leaves a 14px gap between adjacent bands.
  const SECTION_TOP_INSET = 18   // band top below header item top
  const SECTION_TAIL = 4         // previous band's overhang into a section header's item
  const TEXT_TOP_INSET = 2       // legacy text headers: card starts at item+4, stay above it
  const TEXT_TAIL = -2
  const LAST_TAIL = 4            // air under the final section's last card

  function measure() {
    const wrapper = wrapperRef.value
    if (!wrapper) return
    // Geometry comes from the DOM, not store positions: gridstack's packed
    // layout can drift from saved y values (ties, compaction), and sections
    // tiled header→next-header can never overlap by construction.
    const headers = sections.value
      .map(s => ({ s, el: wrapper.querySelector<HTMLElement>(`[data-widget-id="${CSS.escape(s.id)}"]`) }))
      .filter((h): h is { s: typeof h.s; el: HTMLElement } => !!h.el)
      .sort((a, b) => a.el.offsetTop - b.el.offsetTop)
    if (!headers.length) {
      bounds.value = {}
      return
    }
    let maxBottom = 0
    wrapper.querySelectorAll<HTMLElement>('[data-widget-id]').forEach((el) => {
      maxBottom = Math.max(maxBottom, el.offsetTop + el.offsetHeight)
    })
    const next: Record<string, SectionBounds> = {}
    headers.forEach((h, i) => {
      const top = h.el.offsetTop + (h.s.kind === 'section' ? SECTION_TOP_INSET : TEXT_TOP_INSET)
      const nextHeader = headers[i + 1]
      const end = nextHeader
        ? nextHeader.el.offsetTop + (nextHeader.s.kind === 'section' ? SECTION_TAIL : TEXT_TAIL)
        : maxBottom + LAST_TAIL
      if (end <= top) return
      next[h.s.id] = { top, height: end - top }
    })
    bounds.value = next
  }

  let raf = 0
  let settleTimer: ReturnType<typeof setTimeout> | undefined
  function scheduleMeasure() {
    cancelAnimationFrame(raf)
    raf = requestAnimationFrame(measure)
    // gridstack animates item moves (~0.3s CSS transition) — re-measure after
    // it settles so bands land on final positions.
    clearTimeout(settleTimer)
    settleTimer = setTimeout(measure, 360)
  }

  // Any position/size/membership change (drag, resize, add/remove, text
  // auto-resize — all synced to the store by the gridstack change handler).
  watch(
    () => widgets.value.map(w => `${w.id}:${w.position.x},${w.position.y},${w.position.w},${w.position.h}`).join('|'),
    () => nextTick(scheduleMeasure),
  )
  // Header flag/color edits change sections without moving anything.
  watch(sections, () => nextTick(scheduleMeasure))

  // Catches container reflows the store can't see: initial staggered widget
  // mount, window resize, mobile 1-column collapse. The wrapper element can
  // arrive after setup (it lives inside a child component), so attach on watch.
  let resizeObserver: ResizeObserver | undefined
  watch(wrapperRef, (el) => {
    resizeObserver?.disconnect()
    if (!el) return
    resizeObserver = new ResizeObserver(scheduleMeasure)
    resizeObserver.observe(el)
    scheduleMeasure()
  }, { immediate: true })
  onBeforeUnmount(() => {
    resizeObserver?.disconnect()
    cancelAnimationFrame(raf)
    clearTimeout(settleTimer)
  })

  return { sections, bounds, remeasure: scheduleMeasure }
}
