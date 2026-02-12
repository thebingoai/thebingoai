# Implementation Plan 03: Dashboard Page & Components
## GLM-4.7 Code Generation Specification

**Project:** LLM-MD-CLI Web UI (RAG System)
**Scope:** Complete Dashboard implementation with all sub-components
**Backend:** FastAPI with Redis + Pinecone vector DB
**Framework:** React 19 + TypeScript + Tailwind CSS + shadcn/ui

---

## Architecture Overview

### Backend APIs Required
```
GET /api/status
  Response: {
    status: 'healthy' | 'degraded' | 'unhealthy',
    index: {
      name: string,
      total_vectors: number,
      dimension: number,
      namespaces: Record<string, { vector_count: number }>
    },
    embedding_model: string
  }

GET /health/detailed
  Response: {
    status: 'healthy' | 'degraded' | 'unhealthy',
    checks: {
      api: { status: boolean, latency: number },
      redis: { status: boolean, latency: number },
      pinecone: { status: boolean, latency: number },
      pinecone_vectors?: { status: boolean, count: number }
    }
  }

GET /api/jobs?limit=5
  Response: {
    jobs: JobInfo[],
    count: number
  }

JobInfo interface:
  {
    id: string,
    type: 'index' | 'query' | 'export',
    status: 'pending' | 'processing' | 'completed' | 'failed',
    created_at: ISO8601 timestamp,
    updated_at: ISO8601 timestamp,
    progress?: number (0-100),
    result?: Record<string, any>,
    error?: string
  }
```

---

## Component Specifications

### 1. DashboardPage.tsx
**Location:** `src/pages/DashboardPage.tsx`

**Responsibilities:**
- Main container component for dashboard
- Orchestrates data fetching with custom hooks
- Manages responsive layout
- Provides error boundaries and loading states

**Custom Hooks Used:**
```typescript
const { status, loading, error } = useStatus()
const { health, loading: healthLoading, error: healthError } = useDetailedHealth()
const { jobs, loading: jobsLoading, error: jobsError } = useJobs(undefined, 5)
```

**Layout Structure:**
```
Header (title + date/time)
├── Stats Grid (4-col → 2-col → 1-col)
│   ├── Documents Count
│   ├── Total Vectors
│   ├── Namespaces Count
│   └── Queries (system metric)
│
├── Quick Actions Grid (2-col → 1-col)
│   ├── Upload Files Card
│   └── Start Chat Card
│
├── Recent Activity Section
│   └── ActivityList Component
│
└── System Status Section
    └── SystemStatus Component
```

**Responsive Breakpoints:**
- Desktop (≥1024px): 4-col stat grid, 2-col actions
- Tablet (768px-1023px): 2-col stat grid, 1-col actions
- Mobile (<768px): 1-col stat grid, 1-col actions

**Features:**
- Skeleton loading states for all sections
- Empty states with CTAs
- Error boundaries with retry functionality
- Auto-refresh every 30 seconds
- Dark mode support

---

### 2. StatCard.tsx
**Location:** `src/components/dashboard/StatCard.tsx`

**Props Interface:**
```typescript
interface StatCardProps {
  title: string
  value: number
  icon: ReactNode
  trend?: 'up' | 'down' | 'neutral'
  onClick: () => void
  loading?: boolean
  unit?: string
  description?: string
}
```

**Features:**
- **Animated Counter:** Count from 0 to `value` over 1.2s on mount
  - Uses `useEffect` + `setInterval` for smooth animation
  - Easing: ease-out-cubic for natural deceleration
- **Visual Design:**
  - Base styles: `rounded-xl border bg-white dark:bg-slate-900 shadow-card`
  - Hover: `shadow-card-hover` + `-translate-y-1` (2px up)
  - Cursor: pointer on hover
- **Loading State:**
  - Skeleton shimmer effect
  - Pulsing animation
  - Content placeholder
- **Trend Indicator (optional):**
  - Up: green arrow + "+X%" text
  - Down: red arrow + "-X%" text
  - Neutral: dash + "stable" text
- **Icon Placement:**
  - Top-right corner
  - Color matches trend or defaults to primary
  - Size: 24px
- **Click Behavior:**
  - Slight scale animation (1 → 0.98)
  - Navigates to relevant page

**Card Instances:**
```typescript
// Documents
{
  title: 'Documents Indexed',
  value: status?.index.total_vectors || 0,
  icon: <FileText className="w-6 h-6" />,
  onClick: () => navigate('/documents')
}

// Vectors
{
  title: 'Total Vectors',
  value: status?.index.total_vectors || 0,
  icon: <Hash className="w-6 h-6" />,
  onClick: () => navigate('/documents?view=vectors')
}

// Namespaces
{
  title: 'Namespaces',
  value: Object.keys(status?.index.namespaces || {}).length,
  icon: <FolderTree className="w-6 h-6" />,
  onClick: () => navigate('/documents?view=namespaces')
}

// Queries
{
  title: 'Queries Today',
  value: jobs.filter(j => j.type === 'query' && isToday(j.created_at)).length,
  icon: <Search className="w-6 h-6" />,
  onClick: () => navigate('/jobs')
}
```

---

### 3. QuickActionCard.tsx
**Location:** `src/components/dashboard/QuickActionCard.tsx`

**Props Interface:**
```typescript
interface QuickActionCardProps {
  title: string
  description: string
  icon: ReactNode
  onClick: () => void
  variant: 'upload' | 'chat'
}
```

**Features:**
- **Upload Variant:**
  - Drag-drop zone (visual feedback)
  - Shows file icon + instructions
  - Click opens upload modal
  - Drag state: border color change + background highlight
- **Chat Variant:**
  - Large button with arrow icon
  - Navigates to `/chat` on click
  - Shows description of chat functionality
- **Shared Styles:**
  - Base: `rounded-xl border-2 border-dashed p-6 cursor-pointer transition-all`
  - Hover: gradient border + background color shift + shadow elevation
  - Active: scale animation (1 → 0.98)
  - Color scheme: variant-specific (upload: blue, chat: purple)
- **Gradient Borders:**
  - Upload: blue → cyan gradient
  - Chat: purple → pink gradient
- **Dark Mode:** Appropriate color adjustments

---

### 4. ActivityList.tsx
**Location:** `src/components/dashboard/ActivityList.tsx`

**Props Interface:**
```typescript
interface ActivityListProps {
  jobs: JobInfo[]
  loading?: boolean
}
```

**Features:**
- **Status Icon Mapping:**
  ```typescript
  pending → <Clock className="w-4 h-4 text-gray-400" />
  processing → <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
  completed → <CheckCircle className="w-4 h-4 text-green-500" />
  failed → <AlertCircle className="w-4 h-4 text-red-500" />
  ```
- **Row Layout:**
  ```
  [Status Icon] | Description | Relative Time | [Arrow]
  ```
  - Description generated from job type + metadata
  - Relative time: "2 minutes ago", "just now", etc. (use date-fns)
  - Clickable rows with hover effect
- **Row Styles:**
  - Base: `flex items-center p-3 border-b hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors`
  - Active: pointer cursor + shadow on hover
- **Empty State:**
  ```
  "No recent activity"
  "Queries and indexing jobs will appear here"
  [Optional CTA: "Start a query →"]
  ```
- **"View All" Footer:**
  - Links to `/jobs` page
  - Styled as link with arrow icon
- **Loading State:**
  - Skeleton rows (3-5 items)
  - Shimmer effect
  - Placeholder text

**Description Generation:**
```typescript
const getActivityDescription = (job: JobInfo) => {
  const typeLabel = {
    index: 'Indexed documents',
    query: 'Ran semantic search',
    export: 'Exported results'
  }[job.type]

  const statusLabel = {
    pending: 'Queued',
    processing: 'Processing',
    completed: 'Completed',
    failed: 'Failed'
  }[job.status]

  return `${typeLabel} - ${statusLabel}`
}
```

---

### 5. SystemStatus.tsx
**Location:** `src/components/dashboard/SystemStatus.tsx`

**Props Interface:**
```typescript
interface SystemStatusProps {
  health: DetailedHealthResponse
  loading?: boolean
}

interface DetailedHealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  checks: {
    api: { status: boolean, latency: number }
    redis: { status: boolean, latency: number }
    pinecone: { status: boolean, latency: number }
    pinecone_vectors?: { status: boolean, count: number }
  }
}
```

**Features:**
- **2x2 Service Grid Layout:**
  ```
  [API Status]        [Redis Status]
  [Pinecone Status]   [OpenAI Status]
  ```
- **Service Indicator Card:**
  - Status dot (animated):
    - Green: healthy, subtle pulse animation
    - Red: unhealthy, static
    - Yellow: degraded, pulse slower
  - Service name (bold)
  - Status text: "Healthy" / "Unhealthy" / "Degraded"
  - Optional latency: "(45ms)" in smaller text
  - Base styles: `flex items-center gap-3 p-4 rounded-lg bg-slate-50 dark:bg-slate-800`
- **Status Dot Animation:**
  ```css
  .status-dot-healthy {
    background: #10b981;
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }
  .status-dot-unhealthy {
    background: #ef4444;
  }
  .status-dot-degraded {
    background: #f59e0b;
    animation: pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }
  ```
- **Loading State:**
  - Skeleton cards with shimmer
  - Placeholder dots
- **Error Handling:**
  - Missing service: shows as "unknown" with gray dot
  - Display helpful message if health check fails

---

## Type Definitions

### Create `src/types/api.ts`

```typescript
export interface StatusResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  index: {
    name: string
    total_vectors: number
    dimension: number
    namespaces: Record<string, { vector_count: number }>
  }
  embedding_model: string
}

export interface HealthCheck {
  status: boolean
  latency?: number
  count?: number
}

export interface DetailedHealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  checks: {
    api: HealthCheck
    redis: HealthCheck
    pinecone: HealthCheck
    pinecone_vectors?: HealthCheck
  }
}

export interface JobInfo {
  id: string
  type: 'index' | 'query' | 'export'
  status: 'pending' | 'processing' | 'completed' | 'failed'
  created_at: string
  updated_at: string
  progress?: number
  result?: Record<string, any>
  error?: string
}

export interface JobsResponse {
  jobs: JobInfo[]
  count: number
}
```

### Create `src/hooks/useStatus.ts`

```typescript
import { useState, useEffect } from 'react'
import { StatusResponse } from '@/types/api'

export const useStatus = () => {
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await fetch('/api/status')
        if (!response.ok) throw new Error('Failed to fetch status')
        const data = await response.json()
        setStatus(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  return { status, loading, error }
}
```

### Create `src/hooks/useDetailedHealth.ts`

```typescript
import { useState, useEffect } from 'react'
import { DetailedHealthResponse } from '@/types/api'

export const useDetailedHealth = () => {
  const [health, setHealth] = useState<DetailedHealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await fetch('/health/detailed')
        if (!response.ok) throw new Error('Failed to fetch health')
        const data = await response.json()
        setHealth(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }

    fetchHealth()
    const interval = setInterval(fetchHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  return { health, loading, error }
}
```

### Create `src/hooks/useJobs.ts`

```typescript
import { useState, useEffect } from 'react'
import { JobInfo, JobsResponse } from '@/types/api'

export const useJobs = (filter?: string, limit: number = 10) => {
  const [jobs, setJobs] = useState<JobInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        setLoading(true)
        setError(null)
        const params = new URLSearchParams({ limit: limit.toString() })
        if (filter) params.append('filter', filter)

        const response = await fetch(`/api/jobs?${params}`)
        if (!response.ok) throw new Error('Failed to fetch jobs')
        const data: JobsResponse = await response.json()
        setJobs(data.jobs)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }

    fetchJobs()
    const interval = setInterval(fetchJobs, 15000) // Refresh every 15s
    return () => clearInterval(interval)
  }, [filter, limit])

  return { jobs, loading, error }
}
```

---

## UI/UX Standards & Design System

### Card Styles
```typescript
// Base card
const cardClasses = "rounded-xl border bg-white dark:bg-slate-900 shadow-card hover:shadow-card-hover transition-shadow"

// Stat card (with animation)
const statCardClasses = "p-6 cursor-pointer active:scale-98 transition-all"

// Quick action card
const actionCardClasses = "p-6 border-2 border-dashed cursor-pointer transition-all rounded-xl"
```

### Typography
```typescript
// Section headers
const headerClasses = "text-lg font-semibold text-slate-900 dark:text-white mb-4"

// Stat values
const valueClasses = "text-3xl font-bold text-slate-900 dark:text-white"

// Stat labels
const labelClasses = "text-sm text-slate-600 dark:text-slate-400"
```

### Spacing & Layout
```typescript
// Page padding
const pagePadding = "p-6 md:p-8 lg:p-10"  // Desktop, tablet, mobile
const mobilePagePadding = "p-4 md:p-6"

// Section spacing
const sectionSpacing = "space-y-6"

// Grid spacing
const gridSpacing = "grid gap-4 lg:gap-6"
```

### Colors
```typescript
// Status colors
const statusColors = {
  healthy: "text-green-600 bg-green-50 dark:bg-green-900/20",
  degraded: "text-yellow-600 bg-yellow-50 dark:bg-yellow-900/20",
  unhealthy: "text-red-600 bg-red-50 dark:bg-red-900/20"
}

// Variant colors
const variantColors = {
  upload: {
    border: "border-blue-300 dark:border-blue-700",
    bg: "bg-blue-50/50 dark:bg-blue-900/10",
    hover: "hover:border-blue-400 hover:bg-blue-50"
  },
  chat: {
    border: "border-purple-300 dark:border-purple-700",
    bg: "bg-purple-50/50 dark:bg-purple-900/10",
    hover: "hover:border-purple-400 hover:bg-purple-50"
  }
}
```

### Animations
```typescript
// Counter animation: ease-out-cubic over 1.2s
// Hover: -translate-y-1 (2px up)
// Active: scale-98 (98%)
// Loading: pulse 2s
// Status dot pulse: 2s (healthy), 3s (degraded)
```

### Shadows
```typescript
// shadow-card: 0 1px 3px rgba(0,0,0,0.1)
// shadow-card-hover: 0 4px 12px rgba(0,0,0,0.15)
```

---

## Implementation Checklist

### Phase 1: Setup & Types
- [ ] Create `src/types/api.ts` with all interfaces
- [ ] Create custom hooks: `useStatus.ts`, `useDetailedHealth.ts`, `useJobs.ts`
- [ ] Create component directory: `src/components/dashboard/`

### Phase 2: Components
- [ ] Build `StatCard.tsx` with counter animation
- [ ] Build `QuickActionCard.tsx` with variants
- [ ] Build `ActivityList.tsx` with status icons
- [ ] Build `SystemStatus.tsx` with health indicators
- [ ] Test loading and error states for all

### Phase 3: Page Integration
- [ ] Build `DashboardPage.tsx` with layout
- [ ] Integrate all components
- [ ] Implement responsive breakpoints
- [ ] Add empty states and error boundaries
- [ ] Test data fetching and refresh

### Phase 4: Polish & Testing
- [ ] Dark mode verification
- [ ] Mobile responsiveness testing
- [ ] Skeleton loading states
- [ ] Error recovery & retry logic
- [ ] Performance optimization (memoization)
- [ ] Accessibility checks (ARIA labels, contrast)

---

## Notes for Claude Implementation

1. **Counter Animation:** Use `useEffect` + `requestAnimationFrame` for smooth 60fps animation. Implement cubic-ease-out easing function.

2. **Responsive Grid:** Use Tailwind grid utilities:
   - `grid-cols-1 md:grid-cols-2 lg:grid-cols-4`
   - `gap-4 lg:gap-6`

3. **Skeleton Loading:** Create reusable `Skeleton` component:
   ```typescript
   <div className="h-12 bg-slate-200 dark:bg-slate-700 rounded-lg animate-pulse" />
   ```

4. **Relative Time:** Use `date-fns` library:
   ```typescript
   import { formatDistanceToNow } from 'date-fns'
   formatDistanceToNow(new Date(job.created_at), { addSuffix: true })
   ```

5. **Error Boundaries:** Wrap DashboardPage with error boundary. Show fallback UI with retry button.

6. **Auto-refresh:** Use `setInterval` in `useEffect` cleanup pattern. Different intervals for different data (status: 30s, jobs: 15s).

7. **Dark Mode:** Ensure all colors have dark variants using `dark:` prefix.

8. **Accessibility:**
   - Add `aria-label` to icon-only elements
   - Use semantic HTML (button, a, section)
   - Ensure color contrast ratio ≥ 4.5:1
   - Test with screen readers

---

## Files to Generate

```
src/
├── types/
│   └── api.ts
├── hooks/
│   ├── useStatus.ts
│   ├── useDetailedHealth.ts
│   └── useJobs.ts
├── components/
│   └── dashboard/
│       ├── StatCard.tsx
│       ├── QuickActionCard.tsx
│       ├── ActivityList.tsx
│       └── SystemStatus.tsx
└── pages/
    └── DashboardPage.tsx
```

---

## Success Criteria

- [x] All components render without errors
- [x] Data fetches correctly from backend APIs
- [x] Counter animations smooth and perform well
- [x] Responsive layout works at all breakpoints
- [x] Dark mode fully functional
- [x] Loading states display while fetching
- [x] Error states show helpful messages
- [x] Click handlers navigate to correct pages
- [x] Auto-refresh updates data every 30s
- [x] No console warnings or errors
- [x] Accessibility standards met (WCAG 2.1 AA)

