<template>
  <canvas ref="canvasRef" class="block" />
</template>

<script setup lang="ts">
/**
 * Maintenance page background: three layers drawn into a single canvas.
 *
 *   1. Solid bg fill (palette[0])
 *   2. Aurora — two slow-drifting radial gradients of brand purple
 *   3. Tile field — 10px tiles that slowly drift between bg and bg-tint,
 *      gated by a radial vignette mask around the centered card so the
 *      card area stays clean and aurora reads through `backdrop-blur`.
 *
 * No purple in the tile field — purple lives only in the aurora.
 *
 * Respects `prefers-reduced-motion` (single static frame, no rAF).
 */

const props = defineProps<{
  /** Card element used to compute the vignette mask. */
  cardEl: HTMLElement | null
}>()

// ── config ────────────────────────────────────────────────────────────────
const TILE_SIZE = 10
const FLIP_DURATION_MS = 1400
const DRIFT_RATE_BASE = 0.00015 // per tile per frame at mask=1 → ~1% mid-flip
const FADE_BAND_MIN_PX = 220
const FADE_BAND_FRACTION = 0.25 // of min(viewportW, viewportH)

// Tiles: only bg and bg-tint. No purple here.
const TILE_PALETTE = {
  light: ['#FAFAF7', '#F1EEE8'],
  dark: ['#0E0E10', '#16151A'],
} as const

// Aurora colors (rgb tuples for rgba interpolation)
const AURORA = {
  light: {
    primary: '110, 72, 157', // brand #6E489D
    soft: '184, 164, 201', // muted purple
    alphaPrimary: 0.22,
    alphaSoft: 0.14,
  },
  dark: {
    primary: '140, 95, 195', // lifted purple — reads through ink bg
    soft: '95, 65, 135',
    alphaPrimary: 0.38,
    alphaSoft: 0.22,
  },
} as const

const AURORA_T1_SPEED = 0.00002
const AURORA_T2_SPEED = 0.000032
const AURORA_R1_FRAC = 0.65
const AURORA_R2_FRAC = 0.5

// ── state ─────────────────────────────────────────────────────────────────
const canvasRef = ref<HTMLCanvasElement | null>(null)
const colorMode = useColorMode()
const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

let ctx: CanvasRenderingContext2D | null = null
let vw = 0
let vh = 0
let cols = 0
let rows = 0
let totalTiles = 0
let frontIdx: Uint8Array = new Uint8Array(0)
let backIdx: Uint8Array = new Uint8Array(0)
let flipStart: Float64Array = new Float64Array(0)
let mask: Float32Array = new Float32Array(0)
let cardCenterX = 0
let cardCenterY = 0
let cardHalfW = 0
let cardHalfH = 0
let rafId: number | null = null

const palette = computed(() =>
  colorMode.value === 'dark' ? TILE_PALETTE.dark : TILE_PALETTE.light,
)
const aurora = computed(() =>
  colorMode.value === 'dark' ? AURORA.dark : AURORA.light,
)

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

function measureCard() {
  const el = props.cardEl
  if (!el) return
  const r = el.getBoundingClientRect()
  cardCenterX = r.left + r.width / 2
  cardCenterY = r.top + r.height / 2
  cardHalfW = r.width / 2
  cardHalfH = r.height / 2
}

function computeMask() {
  const fadeBandPx = Math.max(FADE_BAND_MIN_PX, Math.min(vw, vh) * FADE_BAND_FRACTION)
  mask = new Float32Array(totalTiles)
  for (let r = 0; r < rows; r++) {
    const y = r * TILE_SIZE + TILE_SIZE / 2
    const dy = Math.abs(y - cardCenterY)
    const eyBase = Math.max(0, dy - cardHalfH) / fadeBandPx
    for (let c = 0; c < cols; c++) {
      const x = c * TILE_SIZE + TILE_SIZE / 2
      const dx = Math.abs(x - cardCenterX)
      const ex = Math.max(0, dx - cardHalfW) / fadeBandPx
      let d = Math.hypot(ex, eyBase)
      if (d >= 1) d = 1
      // smoothstep
      mask[r * cols + c] = d * d * (3 - 2 * d)
    }
  }
}

function initBuffers() {
  frontIdx = new Uint8Array(totalTiles)
  backIdx = new Uint8Array(totalTiles)
  flipStart = new Float64Array(totalTiles)
  // 75% bg, 25% bg-tint
  for (let i = 0; i < totalTiles; i++) {
    frontIdx[i] = Math.random() < 0.25 ? 1 : 0
  }
}

function sizeCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const dpr = window.devicePixelRatio || 1
  vw = window.innerWidth
  vh = window.innerHeight
  canvas.style.width = vw + 'px'
  canvas.style.height = vh + 'px'
  canvas.width = Math.floor(vw * dpr)
  canvas.height = Math.floor(vh * dpr)
  ctx = canvas.getContext('2d', { alpha: false })
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.imageSmoothingEnabled = false
  cols = Math.ceil(vw / TILE_SIZE)
  rows = Math.ceil(vh / TILE_SIZE)
  totalTiles = cols * rows
  initBuffers()
  measureCard()
  computeMask()
}

function drawAurora(now: number) {
  if (!ctx) return
  const a = aurora.value
  const t1 = now * AURORA_T1_SPEED
  const t2 = now * AURORA_T2_SPEED

  // Blob 1 — primary purple, larger
  const b1x = vw * (0.5 + 0.35 * Math.sin(t1))
  const b1y = vh * (0.5 + 0.3 * Math.cos(t1 * 1.3))
  const r1 = Math.max(vw, vh) * AURORA_R1_FRAC
  const g1 = ctx.createRadialGradient(b1x, b1y, 0, b1x, b1y, r1)
  g1.addColorStop(0, `rgba(${a.primary}, ${a.alphaPrimary})`)
  g1.addColorStop(0.6, `rgba(${a.primary}, ${a.alphaPrimary * 0.25})`)
  g1.addColorStop(1, `rgba(${a.primary}, 0)`)
  ctx.fillStyle = g1
  ctx.fillRect(0, 0, vw, vh)

  // Blob 2 — soft, smaller, opposite drift
  const b2x = vw * (0.5 - 0.4 * Math.cos(t2))
  const b2y = vh * (0.5 - 0.28 * Math.sin(t2 * 1.7))
  const r2 = Math.max(vw, vh) * AURORA_R2_FRAC
  const g2 = ctx.createRadialGradient(b2x, b2y, 0, b2x, b2y, r2)
  g2.addColorStop(0, `rgba(${a.soft}, ${a.alphaSoft})`)
  g2.addColorStop(1, `rgba(${a.soft}, 0)`)
  ctx.fillStyle = g2
  ctx.fillRect(0, 0, vw, vh)
}

function drawStatic() {
  if (!ctx) return
  const p = palette.value
  ctx.fillStyle = p[0]
  ctx.fillRect(0, 0, vw, vh)
  drawAurora(performance.now())
  for (let r = 0; r < rows; r++) {
    const y = r * TILE_SIZE
    for (let c = 0; c < cols; c++) {
      const i = r * cols + c
      const m = mask[i]
      if (m === 0) continue
      ctx.globalAlpha = m
      ctx.fillStyle = p[frontIdx[i]]
      ctx.fillRect(c * TILE_SIZE, y, TILE_SIZE, TILE_SIZE)
    }
  }
  ctx.globalAlpha = 1
}

function loop(now: number) {
  if (!ctx) return
  const p = palette.value

  // 1. bg fill
  ctx.fillStyle = p[0]
  ctx.fillRect(0, 0, vw, vh)

  // 2. aurora
  drawAurora(now)

  // 3a. schedule new drifts (bg ↔ bg-tint only)
  for (let i = 0; i < totalTiles; i++) {
    if (flipStart[i] !== 0) continue
    const m = mask[i]
    if (m === 0) continue
    if (Math.random() < DRIFT_RATE_BASE * m) {
      flipStart[i] = now
      backIdx[i] = frontIdx[i] === 0 ? 1 : 0
    }
  }

  // 3b. draw tiles
  const TS = TILE_SIZE
  for (let r = 0; r < rows; r++) {
    const y = r * TS
    for (let c = 0; c < cols; c++) {
      const i = r * cols + c
      const m = mask[i]
      if (m === 0) continue

      let scaleX = 1
      let colorIdx = frontIdx[i]
      const fs = flipStart[i]
      if (fs !== 0) {
        const tNorm = (now - fs) / FLIP_DURATION_MS
        if (tNorm >= 1) {
          frontIdx[i] = backIdx[i]
          flipStart[i] = 0
        }
        else {
          const e = easeInOutCubic(tNorm)
          scaleX = Math.abs(Math.cos(e * Math.PI))
          colorIdx = e < 0.5 ? frontIdx[i] : backIdx[i]
        }
      }
      ctx.globalAlpha = m
      ctx.fillStyle = p[colorIdx]
      const w = TS * scaleX
      ctx.fillRect(c * TS + (TS - w) / 2, y, w, TS)
    }
  }
  ctx.globalAlpha = 1

  rafId = requestAnimationFrame(loop)
}

function start() {
  stop()
  sizeCanvas()
  if (reducedMotion.value) {
    drawStatic()
  }
  else {
    rafId = requestAnimationFrame(loop)
  }
}

function stop() {
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
}

// ── lifecycle ─────────────────────────────────────────────────────────────
onMounted(() => {
  // Wait one frame so card layout settles before measuring
  requestAnimationFrame(() => requestAnimationFrame(start))
})

onBeforeUnmount(stop)

// Resize: re-init grid + mask (debounced)
const debouncedResize = useDebounceFn(() => {
  start()
}, 150)
useEventListener(window, 'resize', debouncedResize)

// Card layout shifts (font load, content change) → re-measure + recompute mask
watch(
  () => props.cardEl,
  (el) => {
    if (!el) return
    const ro = new ResizeObserver(() => {
      measureCard()
      computeMask()
    })
    ro.observe(el)
    onBeforeUnmount(() => ro.disconnect())
  },
  { immediate: true },
)

// Color mode toggle: next frame uses new palette automatically; for
// reduced-motion users, redraw the static frame.
watch(() => colorMode.value, () => {
  if (reducedMotion.value) drawStatic()
})

// Reduced-motion toggle in OS prefs
watch(reducedMotion, () => {
  start()
})
</script>
