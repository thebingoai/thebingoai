import {
  Chart,
  LineController,
  BarController,
  PieController,
  DoughnutController,
  ScatterController,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Legend,
  Tooltip,
  Filler,
  type ChartType as ChartJsType,
  type ChartOptions as ChartJsOptions,
  type ChartDataset,
} from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'
import type { Ref } from 'vue'
import type { ChartConfig, ChartType } from '~/types/chart'

// Register all required Chart.js components once
Chart.register(
  LineController,
  BarController,
  PieController,
  DoughnutController,
  ScatterController,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Legend,
  Tooltip,
  Filler,
  ChartDataLabels
)

const DEFAULT_PALETTE = [
  '#6366f1', // indigo-500
  '#8b5cf6', // violet-500
  '#ec4899', // pink-500
  '#f43f5e', // rose-500
  '#f97316', // orange-500
  '#eab308', // yellow-500
  '#22c55e', // green-500
  '#06b6d4', // cyan-500
]

function resolveChartJsType(type: ChartType): ChartJsType {
  return type === 'area' ? 'line' : (type as ChartJsType)
}

function applyDefaultColors(
  datasets: ChartConfig['data']['datasets'],
  type: ChartType
): ChartDataset[] {
  const isPieOrDoughnut = type === 'pie' || type === 'doughnut'

  return datasets.map((ds, i) => {
    const color = DEFAULT_PALETTE[i % DEFAULT_PALETTE.length]

    if (isPieOrDoughnut) {
      return {
        ...ds,
        backgroundColor: ds.backgroundColor ?? DEFAULT_PALETTE,
        borderColor: ds.borderColor ?? '#fff',
        borderWidth: ds.borderWidth ?? 2,
      } as ChartDataset
    }

    return {
      ...ds,
      backgroundColor: ds.backgroundColor ?? (type === 'area' ? `${color}33` : color),
      borderColor: ds.borderColor ?? color,
      borderWidth: ds.borderWidth ?? 2,
      fill: type === 'area' ? true : ds.fill,
      tension: ds.tension ?? (type === 'line' || type === 'area' ? 0.4 : undefined),
    } as ChartDataset
  })
}

function sortChartData(config: ChartConfig): { labels: string[]; datasets: ChartConfig['data']['datasets'] } {
  const { labels, datasets } = config.data
  const sortBy = config.options?.sortBy
  const sortDir = config.options?.sortDirection ?? 'asc'

  if (!sortBy || sortBy === 'none' || labels.length === 0) {
    return { labels, datasets }
  }

  const indices = labels.map((_, i) => i)
  if (sortBy === 'label') {
    indices.sort((a, b) => sortDir === 'asc'
      ? labels[a].localeCompare(labels[b])
      : labels[b].localeCompare(labels[a]))
  } else {
    const values = datasets[0]?.data ?? []
    indices.sort((a, b) => sortDir === 'asc'
      ? (values[a] as number ?? 0) - (values[b] as number ?? 0)
      : (values[b] as number ?? 0) - (values[a] as number ?? 0))
  }

  return {
    labels: indices.map(i => labels[i]),
    datasets: datasets.map(ds => ({ ...ds, data: indices.map(i => ds.data[i]) })),
  }
}

function buildChartJsOptions(config: ChartConfig, enableAnimation: boolean): ChartJsOptions {
  const opts = config.options ?? {}
  const isPieOrDoughnut = config.type === 'pie' || config.type === 'doughnut'

  const options: ChartJsOptions = {
    responsive: opts.responsive ?? true,
    maintainAspectRatio: opts.maintainAspectRatio ?? false,
    animation: enableAnimation ? undefined : false,
    layout: {
      padding: {
        top: opts.showValues ? 20 : 0,
      },
    },
    plugins: {
      legend: {
        display: opts.showLegend ?? true,
        position: opts.legendPosition ?? 'top',
      },
      tooltip: {
        enabled: opts.showTooltips ?? true,
      },
      datalabels: {
        display: opts.showValues ?? false,
        color: isPieOrDoughnut ? '#fff' : '#374151',
        font: { size: 11, weight: 'bold' as const },
        anchor: isPieOrDoughnut ? 'center' : 'end',
        align: isPieOrDoughnut ? 'center' : 'top',
      },
    },
  }

  if (!isPieOrDoughnut) {
    ;(options as any).scales = {
      x: {
        grid: { display: opts.showGrid ?? true },
        stacked: opts.stacked ?? false,
      },
      y: {
        grid: { display: opts.showGrid ?? true },
        stacked: opts.stacked ?? false,
        grace: opts.showValues ? '20%' : undefined,
      },
    }
    if (opts.indexAxis) {
      ;(options as any).indexAxis = opts.indexAxis
    }
  }

  if (opts.aspectRatio !== undefined) {
    (options as any).aspectRatio = opts.aspectRatio
  }

  return options
}

export function useChart(canvasRef: Ref<HTMLCanvasElement | null>, configRef: Ref<ChartConfig>) {
  let chartInstance: Chart | null = null
  let currentChartJsType: string | null = null

  function createChart() {
    const canvas = canvasRef.value
    if (!canvas) return

    const config = configRef.value
    const enableAnimation = config.animation?.chartAnimation ?? true
    const chartJsType = resolveChartJsType(config.type)
    const sorted = sortChartData(config)
    const datasets = applyDefaultColors(sorted.datasets, config.type)
    const options = buildChartJsOptions(config, enableAnimation)

    chartInstance = new Chart(canvas, {
      type: chartJsType,
      data: {
        labels: sorted.labels,
        datasets,
      },
      options,
    })
    currentChartJsType = chartJsType
  }

  function updateChart() {
    if (!chartInstance) return

    const config = configRef.value
    const sorted = sortChartData(config)
    const datasets = applyDefaultColors(sorted.datasets, config.type)
    const enableAnimation = config.animation?.chartAnimation ?? true
    const options = buildChartJsOptions(config, enableAnimation)

    chartInstance.data.labels = sorted.labels
    chartInstance.data.datasets = datasets as any
    chartInstance.options = options as any
    chartInstance.update()
  }

  function destroyChart() {
    chartInstance?.destroy()
    chartInstance = null
    currentChartJsType = null
  }

  onMounted(() => {
    createChart()
  })

  watch(configRef, () => {
    // If chart type changed, recreate; otherwise just update data
    const newType = resolveChartJsType(configRef.value.type)
    if (chartInstance && currentChartJsType !== newType) {
      destroyChart()
      createChart()
    } else {
      updateChart()
    }
  }, { deep: true })

  onBeforeUnmount(() => {
    destroyChart()
  })
}
