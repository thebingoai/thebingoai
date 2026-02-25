<template>
  <div class="w-full">
    <!-- Loading skeleton -->
    <UiSkeleton v-if="loading" class="h-28 w-full rounded-lg" />

    <!-- Heatmap SVG -->
    <div v-else class="overflow-x-auto">
      <svg
        :viewBox="`0 0 ${svgWidth} ${svgHeight}`"
        :width="svgWidth"
        :height="svgHeight"
        class="block"
        style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;"
      >
        <!-- Month labels -->
        <g>
          <text
            v-for="label in monthLabels"
            :key="`month-${label.x}`"
            :x="label.x + LEFT_OFFSET"
            :y="10"
            font-size="9"
            fill="#57606a"
          >{{ label.text }}</text>
        </g>

        <!-- Day-of-week labels -->
        <g>
          <text
            v-for="day in dayLabels"
            :key="`day-${day.row}`"
            :x="0"
            :y="TOP_OFFSET + day.row * (CELL_SIZE + CELL_GAP) + CELL_SIZE - 1"
            font-size="9"
            fill="#57606a"
          >{{ day.text }}</text>
        </g>

        <!-- Grid cells -->
        <g>
          <rect
            v-for="cell in cells"
            :key="cell.date"
            :x="LEFT_OFFSET + cell.col * (CELL_SIZE + CELL_GAP)"
            :y="TOP_OFFSET + cell.row * (CELL_SIZE + CELL_GAP)"
            :width="CELL_SIZE"
            :height="CELL_SIZE"
            rx="2"
            ry="2"
            :fill="colorForCount(cell.count)"
          >
            <title>{{ tooltipText(cell) }}</title>
          </rect>
        </g>

        <!-- Legend -->
        <g :transform="`translate(${LEFT_OFFSET + svgWidth - LEFT_OFFSET - legendWidth}, ${svgHeight - LEGEND_SIZE - 1})`">
          <text x="0" y="9" font-size="9" fill="#57606a">Less</text>
          <rect
            v-for="(color, i) in COLORS"
            :key="`legend-${i}`"
            :x="28 + i * (LEGEND_SIZE + 2)"
            :y="0"
            :width="LEGEND_SIZE"
            :height="LEGEND_SIZE"
            rx="2"
            ry="2"
            :fill="color"
          />
          <text :x="28 + COLORS.length * (LEGEND_SIZE + 2) + 3" y="9" font-size="9" fill="#57606a">More</text>
        </g>
      </svg>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Cell {
  date: string
  count: number
  col: number
  row: number
}

interface MonthLabel {
  text: string
  x: number
}

interface DayLabel {
  text: string
  row: number
}

const props = withDefaults(defineProps<{
  data: Map<string, number>
  weeks?: number
  loading?: boolean
}>(), {
  weeks: 52,
  loading: false,
})

// Layout constants
const CELL_SIZE = 11
const CELL_GAP = 2
const LEFT_OFFSET = 24   // space for day labels
const TOP_OFFSET = 16    // space for month labels
const LEGEND_SIZE = 10

const COLORS = ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39']

// Computed dimensions
const svgWidth = computed(() => LEFT_OFFSET + (props.weeks + 1) * (CELL_SIZE + CELL_GAP))
const svgHeight = computed(() => TOP_OFFSET + 7 * (CELL_SIZE + CELL_GAP) + LEGEND_SIZE + 6)
const legendWidth = computed(() => 28 + COLORS.length * (LEGEND_SIZE + 2) + 30)

function colorForCount(count: number): string {
  if (count <= 0) return COLORS[0]
  if (count <= 2) return COLORS[1]
  if (count <= 5) return COLORS[2]
  if (count <= 9) return COLORS[3]
  return COLORS[4]
}

function tooltipText(cell: Cell): string {
  if (cell.count === 0) return `No conversations on ${cell.date}`
  const noun = cell.count === 1 ? 'conversation' : 'conversations'
  return `${cell.count} ${noun} on ${cell.date}`
}

// Build 52-week grid starting from the oldest Monday before today
const cells = computed<Cell[]>(() => {
  const today = new Date()
  // Find start: go back (weeks * 7 - 1) days, then back to nearest Monday
  const endDate = new Date(today)
  const startDate = new Date(today)
  startDate.setDate(today.getDate() - (props.weeks * 7 - 1))
  // Align to Monday: (getDay() + 6) % 7 → Mon=0, Tue=1 ... Sun=6
  const dayOfWeek = (startDate.getDay() + 6) % 7
  startDate.setDate(startDate.getDate() - dayOfWeek)

  const result: Cell[] = []
  const cursor = new Date(startDate)

  while (cursor <= endDate) {
    const y = cursor.getFullYear()
    const m = String(cursor.getMonth() + 1).padStart(2, '0')
    const d = String(cursor.getDate()).padStart(2, '0')
    const dateStr = `${y}-${m}-${d}`
    // col = week index from start
    const diffDays = Math.round((cursor.getTime() - startDate.getTime()) / 86400000)
    const col = Math.floor(diffDays / 7)
    const row = (cursor.getDay() + 6) % 7 // Mon=0, Tue=1 ... Sun=6

    result.push({
      date: dateStr,
      count: props.data.get(dateStr) ?? 0,
      col,
      row,
    })

    cursor.setDate(cursor.getDate() + 1)
  }

  return result
})

// Month labels: show month name at first cell of each new month
const monthLabels = computed<MonthLabel[]>(() => {
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const labels: MonthLabel[] = []
  let lastMonth = -1
  let lastCol = -4 // minimum column gap before placing a label

  for (const cell of cells.value) {
    const d = new Date(cell.date + 'T00:00:00')
    const m = d.getMonth()
    if (m !== lastMonth && cell.col - lastCol >= 3) {
      labels.push({ text: MONTHS[m], x: cell.col * (CELL_SIZE + CELL_GAP) })
      lastMonth = m
      lastCol = cell.col
    }
  }

  return labels
})

// Day labels: Mon (row 0), Wed (row 2), Fri (row 4)
const dayLabels = computed<DayLabel[]>(() => [
  { text: 'Mon', row: 0 },
  { text: 'Wed', row: 2 },
  { text: 'Fri', row: 4 },
])
</script>
