import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, computed, watch } from 'vue'

// ── Stub Nuxt auto-imports ───────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)

// ── Mock html2pdf.js (browser-only; no canvas in happy-dom) ──────────
const saveMock = vi.fn().mockResolvedValue(undefined)
const setMock = vi.fn()
const fromMock = vi.fn()
function makeChain() {
  const chain: any = {}
  chain.set = setMock.mockReturnValue(chain)
  chain.from = fromMock.mockReturnValue(chain)
  chain.save = saveMock
  return chain
}
vi.mock('html2pdf.js', () => ({ default: vi.fn(() => makeChain()) }))

import { useBriefingPdf } from '~/composables/useBriefingPdf'

describe('useBriefingPdf', () => {
  beforeEach(() => {
    saveMock.mockClear()
    setMock.mockClear()
    fromMock.mockClear()
  })

  describe('slug', () => {
    it('lowercases, strips punctuation, and hyphenates spaces', () => {
      const { slug } = useBriefingPdf()
      expect(slug('Revenue held flat!')).toBe('revenue-held-flat')
    })

    it('collapses repeated separators and trims edges', () => {
      const { slug } = useBriefingPdf()
      expect(slug('  Q3 — Big   Win  ')).toBe('q3-big-win')
    })

    it('falls back to "briefing" for empty/symbol-only input', () => {
      const { slug } = useBriefingPdf()
      expect(slug('!!!')).toBe('briefing')
      expect(slug('')).toBe('briefing')
    })
  })

  describe('waitForWidgets', () => {
    it('resolves immediately when expected is 0', async () => {
      const { waitForWidgets } = useBriefingPdf()
      await expect(waitForWidgets(0)).resolves.toBeUndefined()
    })

    it('resolves once markWidgetLoaded reaches the expected count', async () => {
      const { waitForWidgets, markWidgetLoaded } = useBriefingPdf()
      let resolved = false
      const p = waitForWidgets(2).then(() => { resolved = true })
      expect(resolved).toBe(false)
      markWidgetLoaded()
      await Promise.resolve()
      expect(resolved).toBe(false)
      markWidgetLoaded()
      await p
      expect(resolved).toBe(true)
    })

    it('resolves on timeout even if widgets never load', async () => {
      vi.useFakeTimers()
      const { waitForWidgets } = useBriefingPdf()
      let resolved = false
      const p = waitForWidgets(3, 8000).then(() => { resolved = true })
      await vi.advanceTimersByTimeAsync(8000)
      await p
      expect(resolved).toBe(true)
      vi.useRealTimers()
    })

    it('resetWidgets zeroes the counter so a later wait blocks again', async () => {
      const { waitForWidgets, markWidgetLoaded, resetWidgets } = useBriefingPdf()
      markWidgetLoaded()
      markWidgetLoaded()
      await waitForWidgets(2) // resolves: count already 2
      resetWidgets()
      let resolved = false
      const p = waitForWidgets(1).then(() => { resolved = true })
      await Promise.resolve()
      expect(resolved).toBe(false) // count back to 0, must wait
      markWidgetLoaded()
      await p
      expect(resolved).toBe(true)
    })
  })

  describe('exportPdf', () => {
    it('generates a PDF with a headline-derived filename and toggles exporting', async () => {
      const { exportPdf, exporting } = useBriefingPdf()
      const html2pdf = (await import('html2pdf.js')).default as unknown as ReturnType<typeof vi.fn>
      const el = {} as HTMLElement

      expect(exporting.value).toBe(false)
      await exportPdf(el, 'Revenue held flat!', 0)

      expect(html2pdf).toHaveBeenCalled()
      expect(setMock).toHaveBeenCalledWith(
        expect.objectContaining({ filename: 'briefing-revenue-held-flat.pdf' }),
      )
      expect(fromMock).toHaveBeenCalledWith(el)
      expect(saveMock).toHaveBeenCalled()
      expect(exporting.value).toBe(false)
    })

    it('is a no-op when already exporting', async () => {
      const { exportPdf, exporting } = useBriefingPdf()
      exporting.value = true
      await exportPdf({} as HTMLElement, 'x', 0)
      expect(saveMock).not.toHaveBeenCalled()
    })

    it('resets exporting to false even if save throws', async () => {
      saveMock.mockRejectedValueOnce(new Error('boom'))
      const { exportPdf, exporting } = useBriefingPdf()
      await exportPdf({} as HTMLElement, 'x', 0)
      expect(exporting.value).toBe(false)
    })
  })
})
