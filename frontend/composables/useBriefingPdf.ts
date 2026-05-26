/**
 * Briefing PDF export. Client-side only.
 *
 * Captures the already-rendered briefing <article> with html2pdf.js
 * (html2canvas + jsPDF) and triggers a download. Waits for async-loaded
 * section widgets (Chart.js canvases) before capturing, and strips dark
 * mode on the cloned document so the PDF is always light.
 */
export function useBriefingPdf() {
  const exporting = ref(false)
  const loadedCount = ref(0)

  /** Page wires this to BriefingWidgetEmbed's @loaded event. */
  function markWidgetLoaded() {
    loadedCount.value += 1
  }

  /** Page calls this when the briefing id changes (page is reused, not remounted). */
  function resetWidgets() {
    loadedCount.value = 0
  }

  /** Turn a headline into a filename-safe slug; fall back to "briefing". */
  function slug(text: string): string {
    const s = (text || '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
    return s || 'briefing'
  }

  /**
   * Resolve once `loadedCount` reaches `expected`, or after `timeoutMs`
   * (export anyway — a stuck widget must not block the download).
   */
  function waitForWidgets(expected: number, timeoutMs = 8000): Promise<void> {
    return new Promise((resolve) => {
      if (loadedCount.value >= expected) {
        resolve()
        return
      }
      const stop = watch(loadedCount, (v: number) => {
        if (v >= expected) {
          stop()
          clearTimeout(timer)
          resolve()
        }
      })
      const timer = setTimeout(() => {
        stop()
        resolve()
      }, timeoutMs)
    })
  }

  /** Wait two animation frames so Chart.js has painted its canvases. */
  function nextFrame(): Promise<void> {
    return new Promise((resolve) => requestAnimationFrame(() => resolve()))
  }

  /**
   * Generate and download the PDF.
   * @param el            the <article> element to capture
   * @param headline      briefing headline (used for the filename)
   * @param expectedWidgets number of sections with a widget_id
   */
  async function exportPdf(
    el: HTMLElement | null,
    headline: string,
    expectedWidgets: number,
  ): Promise<void> {
    if (exporting.value || !el) return
    exporting.value = true
    try {
      await waitForWidgets(expectedWidgets)
      await nextFrame()
      await nextFrame()

      const html2pdf = (await import('html2pdf.js')).default

      await html2pdf()
        .set({
          margin: 12,
          filename: `briefing-${slug(headline)}.pdf`,
          image: { type: 'jpeg', quality: 0.95 },
          html2canvas: {
            scale: 2,
            backgroundColor: '#ffffff',
            useCORS: true,
            // Skip the action-button bar (tagged data-pdf-ignore in the page).
            ignoreElements: (node: Element) =>
              (node as HTMLElement).dataset?.pdfIgnore === 'true',
            // Render the clone in light mode regardless of the live theme.
            // <html> carries `dark` (color-mode) and a `theme-*` paper class
            // (useAppTheme); strip both so the PDF is deterministically light.
            onclone: (doc: Document) =>
              doc.documentElement.classList.remove('dark', 'theme-kraft', 'theme-cool', 'theme-ink'),
          },
          jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
          // Don't use 'avoid-all' — it pushes any block that doesn't fully fit to
          // the next page, leaving large gaps. Let prose/sections flow naturally;
          // only keep charts and the (short) takeaways box from splitting.
          pagebreak: { mode: ['css', 'legacy'], avoid: ['canvas', 'aside'] },
        })
        .from(el)
        .save()
    } catch (e) {
      console.error('Briefing PDF export failed', e)
    } finally {
      exporting.value = false
    }
  }

  return { exporting, markWidgetLoaded, resetWidgets, slug, waitForWidgets, exportPdf }
}
