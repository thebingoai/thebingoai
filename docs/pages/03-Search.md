# Search Page

**Route:** `/search`  
**Purpose:** Vector similarity search across documents  
**Priority:** P0

---

## Wireframe - Initial State

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LLM-MD-CLI                              [🔍 Search...]                   │
├──────────┬──────────────────────────────────────────────────────────────────┤
│          │                                                                  │
│  📊      │                    🔍 Vector Search                              │
│  📄 Docs │                                                                  │
│  🔍 Search│           ┌──────────────────────────────────────────┐          │
│  💬 Chat │           │  🔍  Search your documents...            │          │
│  ⚙️ Jobs │           └──────────────────────────────────────────┘          │
│  ⚙️ Settings│                                                                  │
│          │     Search across 1,234 documents in 12 namespaces              │
│          │                                                                  │
│          │  ┌───────────────────────────────────────────────────────────┐  │
│          │  │  💡 Try searching for:                                     │  │
│          │  │     • "meeting notes from last week"                       │  │
│          │  │     • "API design decisions"                               │  │
│          │  │     • "project roadmap"                                    │  │
│          │  └───────────────────────────────────────────────────────────┘  │
│          │                                                                  │
│          │  Recent Searches                                               │
│          │  ┌───────────────────────────────────────────────────────────┐  │
│          │  │  • embeddings (3 results)           2 hours ago          │  │
│          │  │  • python async patterns (5 results) 1 day ago           │  │
│          │  └───────────────────────────────────────────────────────────┘  │
│          │                                                                  │
└──────────┴──────────────────────────────────────────────────────────────────┘
```

## Wireframe - Search Results

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LLM-MD-CLI                              [🔍 Search...]                   │
├──────────┬──────────────────────────────────────────────────────────────────┤
│          │  🔍 Vector Search                                              │
│  📊      │                                                                  │
│  📄 Docs │  ┌───────────────────────────────────────────────────────────┐  │
│  🔍 Search│  │ 🔍 embeddings in: [All ▼]    Top-K: [5 ▼]    [Search]   │  │
│  💬 Chat │  └───────────────────────────────────────────────────────────┘  │
│  ⚙️ Jobs │                                                                  │
│  ⚙️ Settings│  Filters:  [personal ✕] [work ✕]  [Clear all]                │  │
│          │                                                                  │
│          │  Found 5 results (0.23s)                                       │  │
│          │                                                                  │
│          │  ┌───────────────────────────────────────────────────────────┐  │
│          │  │  📄 personal/notes.md  #chunk-2                           │  │
│          │  │                                                           │  │
│          │  │  ...word embeddings are dense vector representations...   │  │
│          │  │  that capture semantic meaning. OpenAI's text-...         │  │
│          │  │                                                           │  │
│          │  │  Score: 0.92  │  💬 Ask about this                       │  │
│          │  └───────────────────────────────────────────────────────────┘  │
│          │                                                                  │
│          │  ┌───────────────────────────────────────────────────────────┐  │
│          │  │  📄 work/api-design.md  #chunk-5                          │  │
│          │  │                                                           │  │
│          │  │  ...we decided to use embeddings for similarity...        │  │
│          │  │  search rather than keyword matching...                     │  │
│          │  │                                                           │  │
│          │  │  Score: 0.87  │  💬 Ask about this                       │  │
│          │  └───────────────────────────────────────────────────────────┘  │
│          │                                                                  │
│          │  ┌───────────────────────────────────────────────────────────┐  │
│          │  │  📄 projects/ml-notes.md  #chunk-1                        │  │
│          │  │                                                           │  │
│          │  │  Score: 0.81  │  💬 Ask about this                       │  │
│          │  └───────────────────────────────────────────────────────────┘  │
│          │                                                                  │
│          │  [Load more results]                                           │
│          │                                                                  │
└──────────┴──────────────────────────────────────────────────────────────────┘
```

## Wireframe - Filter Panel (Collapsible)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ┌──────────────┐ ┌───────────────────────────────────────────────────────┐ │
│  │ Filters      │ │  Search Results                                       │ │
│  │              │ │                                                       │ │
│  │ Namespaces   │ │  ...                                                  │ │
│  │ ☑️ All        │ │                                                       │ │
│  │ ☑️ personal   │ │                                                       │ │
│  │ ☐ work       │ │                                                       │ │
│  │ ☑️ projects   │ │                                                       │ │
│  │              │ │                                                       │ │
│  │ ──────────── │ │                                                       │ │
│  │              │ │                                                       │ │
│  │ Score Range  │ │                                                       │ │
│  │ Min: 0.7 ───●│ │                                                       │ │
│  │              │ │                                                       │ │
│  │ ──────────── │ │                                                       │ │
│  │              │ │                                                       │ │
│  │ Date Range   │ │                                                       │ │
│  │ ○ All time   │ │                                                       │ │
│  │ ○ Last 24h   │ │                                                       │ │
│  │ ○ Last week  │ │                                                       │ │
│  │ ○ Last month │ │                                                       │ │
│  │              │ │                                                       │ │
│  │ [Apply]      │ │                                                       │ │
│  └──────────────┘ └───────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Layout

- **Full width** centered search bar (top)
- **Filter sidebar** (left, collapsible)
- **Results list** (center, scrollable)

---

## Sections

### 1. Search Bar

**Features:**
- Large, prominent input (centered)
- Placeholder: "Search your documents..."
- Search icon (🔍) inside input
- Clear button (✕) when text entered
- Loading spinner during search
- Autocomplete dropdown (recent searches)

**Keyboard Shortcuts:**
- `Cmd/Ctrl + K` - Focus search
- `Enter` - Execute search
- `Escape` - Clear search

### 2. Filter Panel

**Filters:**

| Filter | Type | Options |
|--------|------|---------|
| Namespaces | Multi-select checkbox | All available namespaces |
| Top-K | Dropdown | 5, 10, 20, 50 |
| Min Score | Slider | 0.0 - 1.0 |
| Date Range | Radio buttons | All time, 24h, week, month |

**Interactions:**
- Click filter header → Expand/collapse
- Active filters show as chips below search bar
- "Clear all" removes all filters

### 3. Results List

**Result Card:**

```
┌─────────────────────────────────────────────────────────────┐
│  📄 {namespace}/{filename}  #{chunk-id}                    │
│                                                             │
│  ...{highlighted matching text}...                         │
│  ...{surrounding context}...                               │
│                                                             │
│  Score: 0.92  │  💬 Ask about this  │  📄 View Document    │
└─────────────────────────────────────────────────────────────┘
```

**Card Elements:**
- Document icon + path
- Chunk identifier
- Content preview (2-3 lines)
- Highlight matching terms (bold)
- Score badge (color-coded)
- Action buttons

**Score Colors:**
| Range | Color | Badge |
|-------|-------|-------|
| 0.90+ | Green | 🟢 Excellent |
| 0.70-0.89 | Blue | 🔵 Good |
| 0.50-0.69 | Yellow | 🟡 Fair |
| <0.50 | Gray | ⚪ Low |

### 4. Result Actions

**Per Result:**
| Action | Icon | Behavior |
|--------|------|----------|
| Ask about this | 💬 | Navigate to chat with context |
| View document | 📄 | Open document preview |
| Copy text | 📋 | Copy result content |

### 5. Search History

**Storage:**
- Save last 20 searches locally
- Include query, filters, timestamp

**Display:**
- Show below search bar when empty
- Click to re-run search
- Clear individual or all history

---

## Components Needed

| Component | File |
|-----------|------|
| SearchInput | `components/search/SearchInput.tsx` |
| FilterPanel | `components/search/FilterPanel.tsx` |
| ResultCard | `components/search/ResultCard.tsx` |
| ResultList | `components/search/ResultList.tsx` |
| ScoreBadge | `components/search/ScoreBadge.tsx` |
| HighlightedText | `components/search/HighlightedText.tsx` |
| SearchHistory | `components/search/SearchHistory.tsx` |

---

## API Endpoints

```typescript
// Vector search
POST /api/query
  Body: {
    query: string;
    namespace?: string;
    top_k: number;
    filter?: object;
  }
  Response: {
    results: Array<{
      id: string;
      content: string;
      score: number;
      metadata: {
        filename: string;
        namespace: string;
        chunk_index: number;
      }
    }>
  }

// Alternative: Simple search
GET /api/search?q={query}&namespace={ns}&limit={n}
```

---

## State Management

```typescript
interface SearchState {
  query: string;
  filters: {
    namespaces: string[];
    topK: number;
    minScore: number;
    dateRange: 'all' | '24h' | 'week' | 'month';
  };
  results: SearchResult[];
  isLoading: boolean;
  error: string | null;
  history: SearchHistoryItem[];
  
  // Actions
  search: (query: string) => Promise<void>;
  setFilters: (filters: Partial<Filters>) => void;
  clearFilters: () => void;
  addToHistory: (query: string) => void;
}
```

---

## Interactions

### Search Flow

1. User types query
2. Debounce 300ms (wait for typing pause)
3. Show loading state
4. Call POST /api/query
5. Display results with fade-in animation
6. Save to history (if successful)

### Result Selection

- Click card → Expand to show more context
- Click "Ask about this" → Navigate to /chat with:
  - Pre-filled question: "Tell me more about..."
  - Selected namespace pre-selected
  - Context from result included

### Filter Application

- Changing filters → Auto-re-search (if query exists)
- URL updates with query params (shareable searches)

---

## Empty States

**No Query:**
- Large search icon
- Placeholder text
- Search suggestions
- Recent history (if any)

**No Results:**
```
┌─────────────────────────────────────┐
│           🔍                        │
│     No results found                │
│                                     │
│  Try:                               │
│  • Using different keywords         │
│  • Checking your spelling           │
│  • Broadening your search           │
│                                     │
│     [Clear Filters]                 │
└─────────────────────────────────────┘
```

---

## URL State

Searches should be shareable via URL:

```
/search?q=embeddings&ns=work,projects&topk=10&minScore=0.7
```

Parameters:
- `q` - Query string
- `ns` - Comma-separated namespaces
- `topk` - Number of results
- `minScore` - Minimum similarity score

On page load, parse URL and execute search automatically.
