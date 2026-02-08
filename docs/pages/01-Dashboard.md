# Dashboard Page

**Route:** `/`  
**Purpose:** Overview and quick actions  
**Priority:** P0

---

## Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LLM-MD-CLI                              [🔍 Search...]    [🌙]    [⚙️]   │
├──────────┬──────────────────────────────────────────────────────────────────┤
│          │  Dashboard                                                    [?]│
│  📊      │                                                                  │
│  📄 Docs │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────┐ │
│  🔍 Search│  │ 📄 Documents │ │ 🔢 Vectors   │ │ 📁 Namespaces│ │ ❓ Queries│ │
│  💬 Chat │  │              │ │              │ │              │ │         │ │
│  ⚙️ Jobs │  │    1,234     │ │    56,789    │ │      12      │ │   89    │ │
│  ⚙️ Settings│  │              │ │              │ │              │ │         │ │
│          │  └──────────────┘ └──────────────┘ └──────────────┘ └─────────┘ │
│          │                                                                  │
│          │  Quick Actions                                                   │
│          │  ┌────────────────────────┐  ┌────────────────────────┐         │
│          │  │    ⬆️ Upload File      │  │    💬 New Chat         │         │
│          │  │                        │  │                        │         │
│          │  │   Drop files here      │  │   Start conversation   │         │
│          │  └────────────────────────┘  └────────────────────────┘         │
│          │                                                                  │
│          │  Recent Activity                                      [View All] │
│          │  ┌────────────────────────────────────────────────────────────┐ │
│          │  │ ⏳ Uploading notes.md...                    2 mins ago  │ │
│          │  │ ✅ Indexed project-docs (23 files)          1 hour ago  │ │
│          │  │ 💬 Chat: "Explain embeddings"               3 hours ago │ │
│          │  │ ⚠️  Failed: large-file.md                   5 hours ago │ │
│          │  └────────────────────────────────────────────────────────────┘ │
│          │                                                                  │
│          │  System Status                                                 │
│          │  ┌────────────────────────────────────────────────────────────┐ │
│          │  │  ✅ Backend     Healthy     ✅ Pinecone    Connected    │ │
│          │  │  ✅ Redis       Connected   ✅ OpenAI      Available    │ │
│          │  └────────────────────────────────────────────────────────────┘ │
│          │                                                                  │
└──────────┴──────────────────────────────────────────────────────────────────┘
```

---

## Layout

- **Full width** content area
- **4-column grid** for stats cards
- **2-column grid** for quick actions
- **Full width** lists for activity and status

---

## Sections

### 1. Stats Cards (4-column grid)

| Card | Metric | Icon | API Endpoint |
|------|--------|------|--------------|
| Documents | Total documents indexed | 📄 | GET /api/status |
| Vectors | Total vectors in Pinecone | 🔢 | GET /api/status |
| Namespaces | Active namespaces | 📁 | GET /api/status |
| Queries | Recent queries count | ❓ | (Track locally) |

**Interactions:**
- Click card → Navigate to respective page
- Hover → Slight elevation shadow
- Auto-refresh every 30s

### 2. Quick Actions (2-column grid)

| Action | Component | Behavior |
|--------|-----------|----------|
| Upload File | DropZone | Opens file picker, drag-drop support |
| New Chat | Button | Navigate to /chat |

**Upload DropZone:**
- Accepts: .md, .txt files
- Max size: 50MB per file
- Shows progress on upload
- Auto-detects namespace

### 3. Recent Activity (List)

**Columns:**
- Status icon (⏳/✅/💬/⚠️)
- Activity description
- Timestamp (relative: "2 mins ago")

**Row Types:**
| Icon | Type | Description |
|------|------|-------------|
| ⏳ | Upload in progress | "Uploading {filename}..." |
| ✅ | Upload complete | "Indexed {namespace} ({n} files)" |
| 💬 | Chat query | "Chat: \"{query snippet}\"" |
| ⚠️ | Error | "Failed: {filename}" |

**Interactions:**
- Click row → Navigate to relevant page
- "View All" link → Navigate to Jobs page

### 4. System Status (Card)

**Services:**
| Service | Status | API |
|---------|--------|-----|
| Backend | Healthy/Unhealthy | GET /health |
| Pinecone | Connected/Disconnected | GET /health/detailed |
| Redis | Connected/Disconnected | GET /health/detailed |
| OpenAI | Available/Unavailable | GET /api/providers |

**Status Indicators:**
- 🟢 Green pulse = Healthy
- 🔴 Red dot = Unhealthy
- 🟡 Yellow = Degraded

---

## Components Needed

| Component | File | Description |
|-----------|------|-------------|
| StatCard | `components/dashboard/StatCard.tsx` | Metric display card |
| QuickActionCard | `components/dashboard/QuickActionCard.tsx` | Action button card |
| ActivityList | `components/dashboard/ActivityList.tsx` | Recent activity feed |
| SystemStatus | `components/dashboard/SystemStatus.tsx` | Health indicators |
| FileDropZone | `components/ui/FileDropZone.tsx` | Drag-drop upload area |

---

## API Endpoints

```typescript
// Dashboard data
GET /health/detailed          // System health
GET /api/status               // Index statistics  
GET /api/jobs?limit=5         // Recent jobs
```

---

## State Management

```typescript
// stores/dashboardStore.ts
interface DashboardState {
  stats: {
    documents: number;
    vectors: number;
    namespaces: number;
    queries: number;
  };
  activities: Activity[];
  systemStatus: SystemStatus;
  refreshStats: () => Promise<void>;
}
```

---

## Responsive Behavior

| Breakpoint | Layout Changes |
|------------|----------------|
| Desktop (≥1280px) | 4-col stats, 2-col actions |
| Tablet (≥768px) | 2-col stats, 1-col actions |
| Mobile (<768px) | 1-col everything, hide sidebar |

---

## Empty States

**No Documents:**
```
┌─────────────────────────────────────┐
│           📄                        │
│     No documents yet                │
│                                     │
│  Upload your first markdown file    │
│  to get started                     │
│                                     │
│     [Upload File]                   │
└─────────────────────────────────────┘
```

---

## Loading States

- Stats cards: Skeleton shimmer
- Activity list: 5 skeleton rows
- Status: Pulsing gray dots

---

## Error Handling

- API error → Toast notification
- Service down → Red banner at top
- Retry button on failed refresh
