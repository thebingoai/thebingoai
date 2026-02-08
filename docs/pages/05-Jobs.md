# Jobs Page

**Route:** `/jobs`  
**Purpose:** Monitor background tasks and uploads  
**Priority:** P1

---

## Wireframe - Jobs List

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LLM-MD-CLI                              [🔍 Search...]                   │
├──────────┬──────────────────────────────────────────────────────────────────┤
│          │  ⚙️ Jobs                                              [⟳ Refresh]│
│  📊      │                                                                  │
│  📄 Docs │  ┌───────────────────────────────────────────────────────────┐  │
│  🔍 Search│  │ Filter: [All Status ▼]  [All Types ▼]  [Last 24h ▼]      │  │
│  💬 Chat │  └───────────────────────────────────────────────────────────┘  │
│  ⚙️ Jobs │                                                                  │
│  ⚙️ Settings│  ┌───────────────────────────────────────────────────────────┐  │
│          │  │ Status │ Type      │ Name           │ Progress   │ Time    │  │
│          │  │────────┼───────────┼────────────────┼────────────┼─────────│  │
│          │  │ 🔄     │ Upload    │ notes.md       │ ████████░░ │ 2m ago  │  │
│          │  │        │           │                │ 80%        │         │  │
│          │  │────────┼───────────┼────────────────┼────────────┼─────────│  │
│          │  │ ⏳     │ Upload    │ large-file.md  │ ░░░░░░░░░░ │ 5m ago  │  │
│          │  │        │           │                │ pending    │         │  │
│          │  │────────┼───────────┼────────────────┼────────────┼─────────│  │
│          │  │ ✅     │ Index     │ work (23)      │ ██████████ │ 1h ago  │  │
│          │  │        │           │                │ 100%       │         │  │
│          │  │────────┼───────────┼────────────────┼────────────┼─────────│  │
│          │  │ ❌     │ Upload    │ invalid.pdf    │ ❌ Failed  │ 2h ago  │  │
│          │  │        │           │                │            │         │  │
│          │  │────────┼───────────┼────────────────┼────────────┼─────────│  │
│          │  │ ✅     │ Query     │ search batch   │ ██████████ │ 3h ago  │  │
│          │  │        │           │                │ 100%       │         │  │
│          │  └───────────────────────────────────────────────────────────┘  │
│          │                                                                  │
│          │  [◀ Prev] Page 1 of 5 [Next ▶]        Showing 5 of 47 jobs      │
│          │                                                                  │
└──────────┴──────────────────────────────────────────────────────────────────┘
```

## Wireframe - Job Detail Modal

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Job Details                                    [✕]                   │  │
│  ├───────────────────────────────────────────────────────────────────────┤  │
│  │                                                                       │  │
│  │  Status:   🔄 Processing                                              │  │
│  │  Type:     Upload                                                     │  │
│  │  ID:       job-550e8400-e29b-41d4-a716-446655440000                   │  │
│  │  Created:  2024-01-15 14:32:18                                        │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  Progress: 80%                                                  │  │  │
│  │  │  █████████████████████████████████████████████████░░░░░░░░░░░░░░ │  │  │
│  │  │  23 of 29 files uploaded                                       │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  Current File: notes.md (2.4 KB)                                     │  │
│  │  Speed: ~150 KB/s                                                    │  │
│  │  ETA: ~2 minutes                                                     │  │
│  │                                                                       │  │
│  │  Recent Logs:                                                        │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
│  │  │ [14:33:02] Started processing batch upload                     │ │  │
│  │  │ [14:33:05] Uploaded: readme.md (success)                       │ │  │
│  │  │ [14:33:08] Uploaded: api.md (success)                          │ │  │
│  │  │ [14:33:12] Uploading: notes.md...                              │ │  │
│  │  │ [14:33:15] Chunking notes.md (3 chunks)                        │ │  │
│  │  └─────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                       │  │
│  │  [Cancel Job]                                    [View Documents]     │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Layout

- **Full width** table for jobs
- **Filter bar** above table
- **Modal** for job details
- **Pagination** below table

---

## Sections

### 1. Filter Bar

**Filters:**

| Filter | Options |
|--------|---------|
| Status | All, Pending, Processing, Completed, Failed, Cancelled |
| Type | All, Upload, Index, Query, Delete |
| Time Range | All time, Last hour, Last 24h, Last week |

**Interactions:**
- Dropdown selectors
- Clear all filters button
- URL sync for shareable filtered views

### 2. Jobs Table

**Columns:**

| Column | Description | Sortable |
|--------|-------------|----------|
| Status | Icon + text badge | Yes |
| Type | Job category | Yes |
| Name | Job identifier | Yes |
| Progress | Progress bar or status | No |
| Time | Created/updated timestamp | Yes |
| Actions | View, Cancel, Retry | No |

**Status Badges:**

| Status | Icon | Color | Description |
|--------|------|-------|-------------|
| Pending | ⏳ | Gray | Waiting to start |
| Processing | 🔄 | Blue | Currently running |
| Completed | ✅ | Green | Finished successfully |
| Failed | ❌ | Red | Error occurred |
| Cancelled | 🚫 | Yellow | User cancelled |

**Row Actions:**
- 👁️ View - Open detail modal
- ✕ Cancel - Stop pending/running job
- 🔄 Retry - Re-run failed job
- 🗑️ Delete - Remove from list

### 3. Job Detail Modal

**Header:**
- Job ID
- Status badge
- Created timestamp

**Progress Section:**
- Percentage
- Visual progress bar
- Current operation
- Items processed / total

**Metrics:**
- Upload speed (if applicable)
- Estimated time remaining
- Time elapsed

**Logs:**
- Scrollable log output
- Timestamps
- Auto-scroll to bottom
- Copy logs button

**Actions:**
- Cancel (if running)
- Retry (if failed)
- View related documents
- Close

### 4. Real-time Updates

**Auto-refresh:**
- Poll every 5 seconds for active jobs
- Visual indicator when new data arrives
- Smooth animation for status changes

**Notifications:**
- Toast when job completes
- Toast when job fails
- Sound option (toggle in settings)

---

## Components Needed

| Component | File |
|-----------|------|
| JobsTable | `components/jobs/JobsTable.tsx` |
| JobRow | `components/jobs/JobRow.tsx` |
| JobStatusBadge | `components/jobs/JobStatusBadge.tsx` |
| JobProgressBar | `components/jobs/JobProgressBar.tsx` |
| JobDetailModal | `components/jobs/JobDetailModal.tsx` |
| JobFilters | `components/jobs/JobFilters.tsx` |
| JobLogs | `components/jobs/JobLogs.tsx` |

---

## API Endpoints

```typescript
// List jobs
GET /api/jobs
  Query: {
    status?: 'pending' | 'processing' | 'completed' | 'failed';
    limit?: number;
    offset?: number;
  }
  Response: {
    jobs: Job[];
    total: number;
  }

// Get single job
GET /api/jobs/{job_id}
  Response: {
    job_id: string;
    status: string;
    type: string;
    name: string;
    progress: number;
    created_at: string;
    updated_at: string;
    error?: string;
    logs: string[];
  }

// Cancel job
POST /api/jobs/{job_id}/cancel

// Retry job
POST /api/jobs/{job_id}/retry
```

---

## State Management

```typescript
interface JobsState {
  jobs: Job[];
  totalJobs: number;
  currentPage: number;
  filters: {
    status: string | null;
    type: string | null;
    timeRange: string;
  };
  selectedJob: Job | null;
  isLoading: boolean;
  autoRefresh: boolean;
  
  // Actions
  fetchJobs: () => Promise<void>;
  cancelJob: (id: string) => Promise<void>;
  retryJob: (id: string) => Promise<void>;
  setFilters: (filters: Partial<Filters>) => void;
  toggleAutoRefresh: () => void;
}
```

---

## Job Types

| Type | Description | Progress Meaning |
|------|-------------|------------------|
| Upload | File upload to backend | Files uploaded / total |
| Index | Document indexing to Pinecone | Documents indexed / total |
| Query | Batch search operation | Queries completed / total |
| Delete | Document deletion | Documents deleted / total |
| Reindex | Refresh index for namespace | Chunks processed / total |

---

## Empty States

**No Jobs:**
```
┌─────────────────────────────────────┐
│           ⚙️                        │
│     No jobs yet                     │
│                                     │
│  Jobs will appear here when you:    │
│  • Upload documents                 │
│  • Run batch operations             │
│  • Re-index namespaces              │
│                                     │
│     [Upload Documents]              │
└─────────────────────────────────────┘
```

**No Matching Filters:**
```
┌─────────────────────────────────────┐
│     No jobs match your filters      │
│                                     │
│     [Clear Filters]                 │
└─────────────────────────────────────┘
```

---

## Responsive

| Breakpoint | Changes |
|------------|---------|
| Desktop | Full table with all columns |
| Tablet | Hide "Type" column, compact rows |
| Mobile | Card list instead of table |

**Mobile Card View:**
```
┌─────────────────────────────────────┐
│ 🔄 Processing                       │
│ Upload: notes.md                    │
│ ████████░░ 80%                      │
│ 2 minutes ago                       │
│ [View] [Cancel]                     │
└─────────────────────────────────────┘
```
