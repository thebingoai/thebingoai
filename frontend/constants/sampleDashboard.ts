import type { Dashboard } from '~/types/dashboard'

export const sampleDashboard: Dashboard = {
  id: 'sample-1',
  title: 'Business Overview',
  description: 'Key metrics across revenue, users, products, and performance',
  createdAt: '2026-03-01',
  widgets: [
    // Row 1: 4 KPI cards (each 3 cols wide, 2 rows tall)
    {
      id: 'kpi-revenue',
      position: { x: 0, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
      widget: {
        type: 'kpi',
        config: {
          value: 1240000,
          label: 'Total Revenue',
          prefix: '$',
          trend: { direction: 'up', value: 12.5, period: 'vs last month' },
          sparkline: [820, 932, 901, 934, 1100, 1170, 1240],
        },
      },
    },
    {
      id: 'kpi-users',
      position: { x: 3, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
      widget: {
        type: 'kpi',
        config: {
          value: 4623,
          label: 'Active Users',
          trend: { direction: 'up', value: 8.2, period: 'vs last month' },
          sparkline: [3200, 3450, 3800, 3950, 4200, 4450, 4623],
        },
      },
    },
    {
      id: 'kpi-conversion',
      position: { x: 6, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
      widget: {
        type: 'kpi',
        config: {
          value: 3.42,
          label: 'Conversion Rate',
          suffix: '%',
          trend: { direction: 'down', value: 0.3, period: 'vs last month' },
          sparkline: [3.8, 3.6, 3.5, 3.7, 3.4, 3.5, 3.42],
        },
      },
    },
    {
      id: 'kpi-aov',
      position: { x: 9, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
      widget: {
        type: 'kpi',
        config: {
          value: 268,
          label: 'Avg. Order Value',
          prefix: '$',
          trend: { direction: 'up', value: 0.1, period: 'vs last month' },
          sparkline: [245, 252, 258, 261, 265, 267, 268],
        },
      },
    },

    // Row 2: Line chart (6 cols) + Bar chart (6 cols)
    {
      id: 'chart-revenue-trend',
      title: 'Monthly Revenue',
      description: 'Revenue trend over the past 6 months',
      position: { x: 0, y: 2, w: 6, h: 4, minW: 3, minH: 3 },
      widget: {
        type: 'chart',
        config: {
          type: 'line',
          title: 'Monthly Revenue',
          data: {
            labels: ['Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'],
            datasets: [
              {
                label: 'Revenue ($k)',
                data: [820, 932, 1100, 960, 1170, 1240],
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99,102,241,0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 4,
              },
            ],
          },
          options: { showLegend: false, showGrid: true, maintainAspectRatio: false },
          animation: { entrance: 'slideUp', entranceDuration: 500 },
        },
      },
    },
    {
      id: 'chart-sales-region',
      title: 'Sales by Region',
      description: 'Units sold per region this quarter',
      position: { x: 6, y: 2, w: 6, h: 4, minW: 3, minH: 3 },
      widget: {
        type: 'chart',
        config: {
          type: 'bar',
          title: 'Sales by Region',
          data: {
            labels: ['North', 'South', 'East', 'West', 'Central'],
            datasets: [
              {
                label: 'Units',
                data: [320, 210, 480, 390, 150],
                backgroundColor: ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe'],
                borderWidth: 0,
              },
            ],
          },
          options: { showLegend: false, showGrid: true, maintainAspectRatio: false },
          animation: { entrance: 'slideUp', entranceDuration: 500, entranceDelay: 80 },
        },
      },
    },

    // Row 3: Full-width data table
    {
      id: 'table-top-products',
      title: 'Top Products',
      position: { x: 0, y: 6, w: 12, h: 5, minW: 4, minH: 3 },
      widget: {
        type: 'table',
        config: {
          columns: [
            { key: 'product', label: 'Product', sortable: true },
            { key: 'revenue', label: 'Revenue', sortable: true, format: 'currency' },
            { key: 'units', label: 'Units Sold', sortable: true, format: 'number' },
            { key: 'growth', label: 'Growth', sortable: true, format: 'percent' },
            { key: 'category', label: 'Category' },
          ],
          rows: [
            { product: 'Enterprise Suite', revenue: 480000, units: 32, growth: 18.2, category: 'Software' },
            { product: 'Pro Plan', revenue: 320000, units: 156, growth: 12.5, category: 'Software' },
            { product: 'Implementation', revenue: 180000, units: 24, growth: 8.1, category: 'Services' },
            { product: 'Hardware Bundle', revenue: 145000, units: 89, growth: -2.3, category: 'Hardware' },
            { product: 'Support Gold', revenue: 95000, units: 210, growth: 5.7, category: 'Support' },
            { product: 'Starter Plan', revenue: 42000, units: 480, growth: 22.4, category: 'Software' },
          ],
          pagination: false,
        },
      },
    },

    // Row 4: Pie chart (4 cols) + Text summary (8 cols)
    {
      id: 'chart-product-mix',
      title: 'Product Mix',
      position: { x: 0, y: 11, w: 4, h: 4, minW: 3, minH: 3 },
      widget: {
        type: 'chart',
        config: {
          type: 'pie',
          title: 'Revenue by Category',
          data: {
            labels: ['Software', 'Services', 'Hardware', 'Support', 'Other'],
            datasets: [
              {
                label: 'Revenue share',
                data: [38, 27, 18, 12, 5],
                backgroundColor: ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#e0e7ff'],
                borderWidth: 0,
              },
            ],
          },
          options: { showLegend: true, legendPosition: 'bottom', maintainAspectRatio: false },
          animation: { entrance: 'fadeIn', entranceDuration: 600, entranceDelay: 160 },
        },
      },
    },
    {
      id: 'text-summary',
      title: 'Executive Summary',
      position: { x: 4, y: 11, w: 8, h: 4, minW: 2, minH: 2 },
      widget: {
        type: 'text',
        config: {
          content: `## Q1 2026 Performance Summary

Revenue reached **$1.24M** in March, up **12.5%** month-over-month and tracking ahead of annual targets.

**Key highlights:**
- Enterprise Suite continues to lead at $480K with 18.2% growth
- Active users crossed 4,600 for the first time
- Starter Plan saw the strongest growth at 22.4%

**Areas to watch:**
- Conversion rate dipped slightly to 3.42% — review onboarding funnel
- Hardware Bundle down 2.3% — supply chain review scheduled for Q2

Overall trajectory remains strong heading into Q2.`,
        },
      },
    },
  ],
}
