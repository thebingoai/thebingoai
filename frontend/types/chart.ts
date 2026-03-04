// Chart type union
export type ChartType = 'line' | 'bar' | 'pie' | 'doughnut' | 'area' | 'scatter'

// Entrance animation types (Anime.js)
export type EntranceAnimation = 'fadeIn' | 'slideUp' | 'grow' | 'none'

// Dataset configuration
export interface DatasetConfig {
  label: string
  data: number[]
  backgroundColor?: string | string[]
  borderColor?: string | string[]
  borderWidth?: number
  fill?: boolean           // for area charts
  tension?: number         // line curve tension (0 = straight, 0.4 = smooth)
  pointRadius?: number
  pointBackgroundColor?: string
}

// Animation configuration
export interface ChartAnimationConfig {
  entrance?: EntranceAnimation   // container animation via Anime.js
  entranceDuration?: number      // ms, default 600
  entranceDelay?: number         // ms, default 0
  chartAnimation?: boolean       // Chart.js data animations, default true
}

// Chart-level options
export interface ChartOptions {
  responsive?: boolean           // default true
  maintainAspectRatio?: boolean  // default true
  aspectRatio?: number           // default 2
  showLegend?: boolean           // default true
  legendPosition?: 'top' | 'bottom' | 'left' | 'right'
  showGrid?: boolean             // default true
  showTooltips?: boolean         // default true
  stacked?: boolean              // for bar/line charts
  indexAxis?: 'x' | 'y'         // horizontal bar charts
  sortBy?: 'none' | 'label' | 'value'
  sortDirection?: 'asc' | 'desc'
  showValues?: boolean             // default false
}

// Main chart config — the JSON spec AI will generate
export interface ChartConfig {
  type: ChartType
  title?: string
  description?: string           // for narrative cards (future)
  data: {
    labels: string[]
    datasets: DatasetConfig[]
  }
  options?: ChartOptions
  animation?: ChartAnimationConfig
}

export interface DashboardConfig {
  id: string
  title: string
  description?: string
  charts: ChartConfig[]
  createdAt?: string
  updatedAt?: string
}
