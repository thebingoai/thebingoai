# IMPLEMENTATION PLAN: Search Page & Components (GLM-4.7)

## Overview
Complete implementation of the Search page for LLM-MD-CLI Web UI, a RAG system for indexing/querying markdown files. Includes all search-specific components with production-ready code.

---

## Backend APIs Reference

### POST /api/query
```
Body: {
  query: string,
  namespace?: string,
  top_k?: number (1-100),
  filter?: object
}

Response: {
  query: string,
  results: [{
    id: string,
    score: number,
    source: string,
    chunk_index: number,
    text: string,
    created_at?: string
  }],
  namespace: string,
  total_results: number
}
```

### GET /api/search
```
Query params: ?q=X&namespace=Y&limit=Z

Response: Same as POST /api/query
```

---

## Component Architecture

```
SearchPage
  ├── SearchInput
  │   ├── SearchHistory (dropdown)
  │   └── Recent searches autocomplete
  ├── FilterPanel
  │   ├── Namespace selector
  │   ├── Top-K dropdown
  │   ├── Min Score slider
  │   ├── Date Range radio
  │   └── Filter chips
  ├── ResultList
  │   ├── ResultCard (x N)
  │   │   ├── Score badge
  │   │   ├── "Ask about this" button
  │   │   └── "View Document" button
  │   ├── Loading skeleton
  │   └── Empty state
  └── SearchHistory (when empty)
```

---

## 1. SearchPage.tsx

**Location:** `src/pages/SearchPage.tsx`

**Responsibilities:**
- Main search page layout
- URL state synchronization
- Auto-execute search on mount if query present
- Keyboard shortcuts (Cmd+K)
- Integrate all child components

```typescript
import React, { useEffect, useCallback, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useSearch } from '@/hooks/useSearch';
import { useSearchStore } from '@/store/searchStore';
import { useNamespaces } from '@/hooks/useNamespaces';
import SearchInput from '@/components/search/SearchInput';
import FilterPanel from '@/components/search/FilterPanel';
import ResultList from '@/components/search/ResultList';
import SearchHistory from '@/components/search/SearchHistory';

interface SearchState {
  query: string;
  namespaces: string[];
  topK: number;
  minScore: number;
  dateRange: 'all' | '24h' | 'week' | 'month';
}

export const SearchPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const searchMutation = useSearch();
  const { addSearch, history, clearHistory } = useSearchStore();
  const { data: namespaceList = [] } = useNamespaces();

  const [state, setState] = useState<SearchState>({
    query: searchParams.get('q') || '',
    namespaces: (searchParams.get('ns') || '').split(',').filter(Boolean),
    topK: parseInt(searchParams.get('topk') || '20'),
    minScore: parseFloat(searchParams.get('minScore') || '0'),
    dateRange: (searchParams.get('dateRange') || 'all') as SearchState['dateRange'],
  });

  // Sync URL params when state changes
  const syncUrl = useCallback((newState: SearchState) => {
    const params = new URLSearchParams();
    if (newState.query) params.set('q', newState.query);
    if (newState.namespaces.length > 0) params.set('ns', newState.namespaces.join(','));
    if (newState.topK !== 20) params.set('topk', newState.topK.toString());
    if (newState.minScore > 0) params.set('minScore', newState.minScore.toString());
    if (newState.dateRange !== 'all') params.set('dateRange', newState.dateRange);

    setSearchParams(params);
  }, [setSearchParams]);

  // Execute search
  const executeSearch = useCallback((searchState: SearchState) => {
    if (!searchState.query.trim()) {
      return;
    }

    addSearch({
      query: searchState.query,
      namespaces: searchState.namespaces,
      resultCount: 0,
    });

    searchMutation.mutate({
      query: searchState.query,
      namespace: searchState.namespaces.join(','),
      top_k: searchState.topK,
      filter: {
        minScore: searchState.minScore,
        dateRange: searchState.dateRange,
      },
    });
  }, [searchMutation, addSearch]);

  // Handle query change
  const handleQueryChange = useCallback((query: string) => {
    const newState = { ...state, query };
    setState(newState);
    syncUrl(newState);
  }, [state, syncUrl]);

  // Handle filter changes (auto-search if query exists)
  const handleFilterChange = useCallback((filter: Partial<SearchState>) => {
    const newState = { ...state, ...filter };
    setState(newState);
    syncUrl(newState);

    if (newState.query.trim()) {
      executeSearch(newState);
    }
  }, [state, syncUrl, executeSearch]);

  // Handle search submission (from input or button)
  const handleSearch = useCallback(() => {
    executeSearch(state);
  }, [state, executeSearch]);

  // Handle history selection
  const handleHistorySelect = useCallback((historyItem: any) => {
    const newState = {
      ...state,
      query: historyItem.query,
      namespaces: historyItem.namespaces || [],
    };
    setState(newState);
    syncUrl(newState);
    executeSearch(newState);
  }, [state, syncUrl, executeSearch]);

  // Auto-search on mount if query present
  useEffect(() => {
    if (state.query.trim()) {
      executeSearch(state);
    }
  }, []); // Run once on mount

  // Keyboard shortcut: Cmd/Ctrl+K focuses search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('search-input') as HTMLInputElement;
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const isSearching = state.query.trim().length > 0;
  const results = searchMutation.data?.results || [];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <div className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-8">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold text-slate-900">Search Documents</h1>
            <p className="text-slate-600">
              Press <kbd className="px-2 py-1 bg-slate-100 border border-slate-300 rounded text-xs font-mono">⌘K</kbd> to search
            </p>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* Search Input */}
        <div className="mb-8">
          <SearchInput
            id="search-input"
            value={state.query}
            onChange={handleQueryChange}
            onSearch={handleSearch}
            isLoading={searchMutation.isPending}
            onHistorySelect={handleHistorySelect}
            history={history}
          />
        </div>

        {/* Show filters or history */}
        {isSearching ? (
          <>
            {/* Filter Panel */}
            <div className="mb-8">
              <FilterPanel
                state={state}
                onFilterChange={handleFilterChange}
                namespaceList={namespaceList}
              />
            </div>

            {/* Results */}
            <ResultList
              results={results}
              loading={searchMutation.isPending}
              query={state.query}
              minScore={state.minScore}
            />
          </>
        ) : (
          /* Search History / Empty State */
          <SearchHistory
            history={history}
            onSelect={handleHistorySelect}
            onClear={clearHistory}
          />
        )}
      </div>
    </div>
  );
};

export default SearchPage;
```

---

## 2. SearchInput.tsx

**Location:** `src/components/search/SearchInput.tsx`

**Responsibilities:**
- Large, prominent search input
- Clear button, loading spinner
- Debounced search on input change
- Submit on Enter key
- Autocomplete from recent searches

```typescript
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { SearchIcon, XIcon, LoaderIcon } from 'lucide-react';
import { debounce } from '@/utils/debounce';

interface SearchHistoryItem {
  query: string;
  namespaces: string[];
  resultCount: number;
  timestamp: number;
}

interface SearchInputProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  onSearch: () => void;
  isLoading?: boolean;
  onHistorySelect?: (item: SearchHistoryItem) => void;
  history?: SearchHistoryItem[];
}

export const SearchInput: React.FC<SearchInputProps> = ({
  id = 'search-input',
  value,
  onChange,
  onSearch,
  isLoading = false,
  onHistorySelect,
  history = [],
}) => {
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Debounced search
  const debouncedSearch = useCallback(
    debounce(() => {
      onSearch();
    }, 300),
    [onSearch]
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value);
    if (e.target.value.trim()) {
      setShowSuggestions(true);
      debouncedSearch();
    } else {
      setShowSuggestions(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      setShowSuggestions(false);
      onSearch();
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  const handleClear = () => {
    onChange('');
    setShowSuggestions(false);
    inputRef.current?.focus();
  };

  const handleSuggestionClick = (item: SearchHistoryItem) => {
    onChange(item.query);
    setShowSuggestions(false);
    if (onHistorySelect) {
      onHistorySelect(item);
    }
  };

  // Click outside to close suggestions
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredSuggestions = history
    .filter((item) =>
      item.query.toLowerCase().includes(value.toLowerCase())
    )
    .slice(0, 8);

  return (
    <div ref={containerRef} className="relative">
      {/* Search Input */}
      <div className="relative">
        <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">
          {isLoading ? (
            <LoaderIcon className="w-5 h-5 animate-spin" />
          ) : (
            <SearchIcon className="w-5 h-5" />
          )}
        </div>

        <input
          ref={inputRef}
          id={id}
          type="text"
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (value.trim() && history.length > 0) {
              setShowSuggestions(true);
            }
          }}
          placeholder="Search your documents..."
          className={`
            w-full
            text-lg
            px-12
            py-4
            rounded-xl
            border-2
            border-slate-200
            bg-white
            transition-all
            duration-200
            focus:outline-none
            focus:border-blue-500
            focus:shadow-lg
            focus:shadow-blue-500/10
            placeholder-slate-400
            disabled:bg-slate-50
            disabled:text-slate-500
          `}
          disabled={isLoading}
        />

        {/* Clear Button */}
        {value && !isLoading && (
          <button
            onClick={handleClear}
            className="absolute right-4 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 transition-colors"
            aria-label="Clear search"
          >
            <XIcon className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Suggestions Dropdown */}
      {showSuggestions && filteredSuggestions.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-slate-200 rounded-lg shadow-lg z-50">
          <ul className="py-2">
            {filteredSuggestions.map((item, index) => (
              <li key={`${item.query}-${index}`}>
                <button
                  onClick={() => handleSuggestionClick(item)}
                  className="w-full text-left px-4 py-2.5 hover:bg-slate-50 transition-colors flex items-center justify-between group"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-slate-900 truncate">
                      {item.query}
                    </div>
                    <div className="text-xs text-slate-500">
                      {item.resultCount} results
                    </div>
                  </div>
                  <div className="ml-2 text-xs text-slate-400 group-hover:text-slate-600">
                    ↵
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default SearchInput;
```

---

## 3. FilterPanel.tsx

**Location:** `src/components/search/FilterPanel.tsx`

**Responsibilities:**
- Horizontal filter bar (below search)
- Multiple filters: namespace, top-k, min score, date range
- Active filters as removable chips
- Auto-search on filter change

```typescript
import React, { useState } from 'react';
import { ChevronDownIcon, XIcon } from 'lucide-react';

interface FilterPanelProps {
  state: {
    query: string;
    namespaces: string[];
    topK: number;
    minScore: number;
    dateRange: 'all' | '24h' | 'week' | 'month';
  };
  onFilterChange: (filter: Partial<any>) => void;
  namespaceList: string[];
}

export const FilterPanel: React.FC<FilterPanelProps> = ({
  state,
  onFilterChange,
  namespaceList,
}) => {
  const [showNamespaceDropdown, setShowNamespaceDropdown] = useState(false);
  const [showTopKDropdown, setShowTopKDropdown] = useState(false);
  const [showDateRangeDropdown, setShowDateRangeDropdown] = useState(false);

  const hasActiveFilters =
    state.namespaces.length > 0 ||
    state.topK !== 20 ||
    state.minScore > 0 ||
    state.dateRange !== 'all';

  const dateRangeLabels: Record<string, string> = {
    all: 'All time',
    '24h': 'Last 24 hours',
    week: 'Last week',
    month: 'Last month',
  };

  const handleNamespaceToggle = (ns: string) => {
    const newNamespaces = state.namespaces.includes(ns)
      ? state.namespaces.filter((n) => n !== ns)
      : [...state.namespaces, ns];
    onFilterChange({ namespaces: newNamespaces });
  };

  const handleRemoveNamespace = (ns: string) => {
    const newNamespaces = state.namespaces.filter((n) => n !== ns);
    onFilterChange({ namespaces: newNamespaces });
  };

  const handleClearAll = () => {
    onFilterChange({
      namespaces: [],
      topK: 20,
      minScore: 0,
      dateRange: 'all',
    });
  };

  return (
    <div className="space-y-4">
      {/* Filter Controls */}
      <div className="flex flex-wrap gap-3">
        {/* Namespace Filter */}
        <div className="relative">
          <button
            onClick={() => setShowNamespaceDropdown(!showNamespaceDropdown)}
            className="px-4 py-2 rounded-lg bg-slate-100 border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-200 transition-colors flex items-center gap-2"
          >
            Namespace
            <ChevronDownIcon className="w-4 h-4" />
          </button>

          {showNamespaceDropdown && (
            <div className="absolute top-full left-0 mt-2 bg-white border border-slate-200 rounded-lg shadow-lg z-50 min-w-48">
              <div className="p-3 space-y-2">
                {namespaceList.length > 0 ? (
                  namespaceList.map((ns) => (
                    <label key={ns} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={state.namespaces.includes(ns)}
                        onChange={() => handleNamespaceToggle(ns)}
                        className="w-4 h-4 rounded border-slate-300 text-blue-600"
                      />
                      <span className="text-sm text-slate-700">{ns}</span>
                    </label>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">No namespaces available</p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Top-K Filter */}
        <div className="relative">
          <button
            onClick={() => setShowTopKDropdown(!showTopKDropdown)}
            className="px-4 py-2 rounded-lg bg-slate-100 border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-200 transition-colors flex items-center gap-2"
          >
            Results ({state.topK})
            <ChevronDownIcon className="w-4 h-4" />
          </button>

          {showTopKDropdown && (
            <div className="absolute top-full left-0 mt-2 bg-white border border-slate-200 rounded-lg shadow-lg z-50">
              <div className="p-2">
                {[5, 10, 20, 50].map((k) => (
                  <button
                    key={k}
                    onClick={() => {
                      onFilterChange({ topK: k });
                      setShowTopKDropdown(false);
                    }}
                    className={`w-full text-left px-4 py-2 rounded text-sm transition-colors ${
                      state.topK === k
                        ? 'bg-blue-100 text-blue-700 font-medium'
                        : 'text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    {k} results
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Min Score Slider */}
        <div className="px-4 py-2 rounded-lg bg-slate-100 border border-slate-200 flex items-center gap-3">
          <label htmlFor="minScore" className="text-sm font-medium text-slate-700">
            Min Score:
          </label>
          <input
            id="minScore"
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={state.minScore}
            onChange={(e) => onFilterChange({ minScore: parseFloat(e.target.value) })}
            className="w-24 h-2 bg-slate-300 rounded-lg appearance-none cursor-pointer"
          />
          <span className="text-sm font-medium text-slate-700 min-w-[2.5rem]">
            {state.minScore.toFixed(1)}
          </span>
        </div>

        {/* Date Range Filter */}
        <div className="relative">
          <button
            onClick={() => setShowDateRangeDropdown(!showDateRangeDropdown)}
            className="px-4 py-2 rounded-lg bg-slate-100 border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-200 transition-colors flex items-center gap-2"
          >
            {dateRangeLabels[state.dateRange]}
            <ChevronDownIcon className="w-4 h-4" />
          </button>

          {showDateRangeDropdown && (
            <div className="absolute top-full left-0 mt-2 bg-white border border-slate-200 rounded-lg shadow-lg z-50">
              <div className="p-2">
                {Object.entries(dateRangeLabels).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => {
                      onFilterChange({ dateRange: key });
                      setShowDateRangeDropdown(false);
                    }}
                    className={`w-full text-left px-4 py-2 rounded text-sm transition-colors ${
                      state.dateRange === key
                        ? 'bg-blue-100 text-blue-700 font-medium'
                        : 'text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Active Filter Chips */}
      {hasActiveFilters && (
        <div className="flex flex-wrap gap-2">
          {state.namespaces.map((ns) => (
            <div
              key={ns}
              className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-blue-50 text-blue-700 text-sm font-medium"
            >
              {ns}
              <button
                onClick={() => handleRemoveNamespace(ns)}
                className="ml-1 p-0.5 hover:bg-blue-100 rounded transition-colors"
                aria-label={`Remove ${ns} filter`}
              >
                <XIcon className="w-3 h-3" />
              </button>
            </div>
          ))}

          {state.topK !== 20 && (
            <div className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-green-50 text-green-700 text-sm font-medium">
              {state.topK} results
              <button
                onClick={() => onFilterChange({ topK: 20 })}
                className="ml-1 p-0.5 hover:bg-green-100 rounded transition-colors"
              >
                <XIcon className="w-3 h-3" />
              </button>
            </div>
          )}

          {state.minScore > 0 && (
            <div className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-purple-50 text-purple-700 text-sm font-medium">
              Score ≥ {state.minScore.toFixed(1)}
              <button
                onClick={() => onFilterChange({ minScore: 0 })}
                className="ml-1 p-0.5 hover:bg-purple-100 rounded transition-colors"
              >
                <XIcon className="w-3 h-3" />
              </button>
            </div>
          )}

          {state.dateRange !== 'all' && (
            <div className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-amber-50 text-amber-700 text-sm font-medium">
              {dateRangeLabels[state.dateRange]}
              <button
                onClick={() => onFilterChange({ dateRange: 'all' })}
                className="ml-1 p-0.5 hover:bg-amber-100 rounded transition-colors"
              >
                <XIcon className="w-3 h-3" />
              </button>
            </div>
          )}

          {/* Clear All Button */}
          <button
            onClick={handleClearAll}
            className="ml-2 text-sm font-medium text-slate-600 hover:text-slate-900 underline"
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  );
};

export default FilterPanel;
```

---

## 4. ResultCard.tsx

**Location:** `src/components/search/ResultCard.tsx`

**Responsibilities:**
- Display individual search result
- Score badge with color-coding
- Content preview with highlighting
- Action buttons (Ask about, View document)
- Expandable full content

```typescript
import React, { useState } from 'react';
import { ChevronDownIcon, ChevronUpIcon, FileIcon, ZapIcon, EyeIcon } from 'lucide-react';

interface QueryResult {
  id: string;
  score: number;
  source: string;
  chunk_index: number;
  text: string;
  created_at?: string;
}

interface ResultCardProps {
  result: QueryResult;
  query?: string;
  onAskAbout?: (result: QueryResult) => void;
  onViewDocument?: (source: string, chunkIndex: number) => void;
}

export const ResultCard: React.FC<ResultCardProps> = ({
  result,
  query = '',
  onAskAbout,
  onViewDocument,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  // Determine score badge color and label
  const getScoreBadge = (score: number) => {
    if (score >= 0.9) {
      return { bg: 'bg-green-100', text: 'text-green-800', label: 'Excellent' };
    } else if (score >= 0.7) {
      return { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Good' };
    } else if (score >= 0.5) {
      return { bg: 'bg-amber-100', text: 'text-amber-800', label: 'Fair' };
    } else {
      return { bg: 'bg-slate-100', text: 'text-slate-800', label: 'Low' };
    }
  };

  const scoreBadge = getScoreBadge(result.score);

  // Extract filename from source path
  const filename = result.source.split('/').pop() || result.source;
  const namespace = result.source.includes('/') ? result.source.split('/')[0] : 'default';

  // Highlight matching terms in preview text
  const highlightText = (text: string, searchQuery: string) => {
    if (!searchQuery.trim()) return text;

    const regex = new RegExp(`(${searchQuery.split(/\s+/).join('|')})`, 'gi');
    const parts = text.split(regex);

    return (
      <span>
        {parts.map((part, idx) =>
          regex.test(part) ? (
            <mark key={idx} className="bg-yellow-200 font-semibold">
              {part}
            </mark>
          ) : (
            <span key={idx}>{part}</span>
          )
        )}
      </span>
    );
  };

  // Get preview (2-3 lines)
  const previewText = result.text
    .split('\n')
    .slice(0, 3)
    .join(' ')
    .substring(0, 200)
    .trimEnd() + (result.text.length > 200 ? '...' : '');

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5 hover:shadow-md hover:border-slate-300 transition-all duration-200 group">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <FileIcon className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <span className="text-sm font-semibold text-slate-900 truncate">
              {namespace}/{filename}
            </span>
            <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded whitespace-nowrap">
              #{result.chunk_index}
            </span>
          </div>
        </div>

        {/* Score Badge */}
        <div
          className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${scoreBadge.bg} ${scoreBadge.text}`}
        >
          {result.score.toFixed(2)} - {scoreBadge.label}
        </div>
      </div>

      {/* Content Preview */}
      <div className="mb-4">
        <p className="text-slate-700 text-sm leading-relaxed">
          {highlightText(previewText, query)}
        </p>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="mb-4 p-4 bg-slate-50 rounded-lg border border-slate-200 max-h-96 overflow-y-auto">
          <p className="text-slate-700 text-sm whitespace-pre-wrap leading-relaxed">
            {highlightText(result.text, query)}
          </p>
        </div>
      )}

      {/* Footer - Actions */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-sm font-medium text-blue-600 hover:text-blue-700 flex items-center gap-1 transition-colors"
        >
          {isExpanded ? (
            <>
              <ChevronUpIcon className="w-4 h-4" />
              Show less
            </>
          ) : (
            <>
              <ChevronDownIcon className="w-4 h-4" />
              Show more
            </>
          )}
        </button>

        <div className="flex items-center gap-2">
          {onAskAbout && (
            <button
              onClick={() => onAskAbout(result)}
              className="px-3 py-1.5 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 text-sm font-medium transition-colors flex items-center gap-1"
            >
              <ZapIcon className="w-4 h-4" />
              Ask about
            </button>
          )}

          {onViewDocument && (
            <button
              onClick={() => onViewDocument(result.source, result.chunk_index)}
              className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 text-sm font-medium transition-colors flex items-center gap-1"
            >
              <EyeIcon className="w-4 h-4" />
              View
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ResultCard;
```

---

## 5. ResultList.tsx

**Location:** `src/components/search/ResultList.tsx`

**Responsibilities:**
- Map results to ResultCard components
- Loading skeleton state
- Empty state message
- Results count and search time
- Filter by minScore

```typescript
import React from 'react';
import { AlertCircleIcon, SearchIcon } from 'lucide-react';
import ResultCard from './ResultCard';

interface QueryResult {
  id: string;
  score: number;
  source: string;
  chunk_index: number;
  text: string;
  created_at?: string;
}

interface ResultListProps {
  results: QueryResult[];
  loading?: boolean;
  query?: string;
  minScore?: number;
  onAskAbout?: (result: QueryResult) => void;
  onViewDocument?: (source: string, chunkIndex: number) => void;
}

const SkeletonCard: React.FC = () => (
  <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-3 animate-pulse">
    <div className="h-4 bg-slate-200 rounded w-3/4" />
    <div className="space-y-2">
      <div className="h-3 bg-slate-200 rounded" />
      <div className="h-3 bg-slate-200 rounded w-5/6" />
    </div>
    <div className="flex gap-2 pt-2">
      <div className="h-8 bg-slate-200 rounded w-24" />
      <div className="h-8 bg-slate-200 rounded w-24" />
    </div>
  </div>
);

export const ResultList: React.FC<ResultListProps> = ({
  results,
  loading = false,
  query = '',
  minScore = 0,
  onAskAbout,
  onViewDocument,
}) => {
  // Filter results by minScore
  const filteredResults = results.filter((r) => r.score >= minScore);

  // Render loading skeleton
  if (loading) {
    return (
      <div className="space-y-4">
        <div className="text-sm font-medium text-slate-600">Searching...</div>
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  }

  // Render empty state
  if (filteredResults.length === 0) {
    return (
      <div className="bg-white border border-slate-200 rounded-lg p-12 text-center">
        <SearchIcon className="w-12 h-12 text-slate-400 mx-auto mb-4 opacity-50" />
        <h3 className="text-lg font-semibold text-slate-900 mb-2">No results found</h3>
        <p className="text-slate-600 mb-6">
          {query
            ? `No documents match your search "${query}". Try different keywords or adjust your filters.`
            : 'Start searching to find relevant documents.'}
        </p>
        {minScore > 0 && (
          <p className="text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded-lg p-3">
            <AlertCircleIcon className="w-4 h-4 inline mr-2" />
            No results meet your minimum score filter ({minScore.toFixed(1)}). Try lowering it.
          </p>
        )}

        {/* Suggestions */}
        {query && (
          <div className="mt-8 pt-8 border-t border-slate-200">
            <p className="text-sm font-medium text-slate-700 mb-4">Suggestions:</p>
            <ul className="text-sm text-slate-600 space-y-2 text-left inline-block">
              <li>• Check your spelling and grammar</li>
              <li>• Try more general keywords</li>
              <li>• Remove specific filters temporarily</li>
              <li>• Try different search terms</li>
            </ul>
          </div>
        )}
      </div>
    );
  }

  // Render results
  return (
    <div className="space-y-4">
      {/* Results Header */}
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-slate-700">
          <span className="text-lg font-bold text-slate-900">{filteredResults.length}</span>
          {' '}
          result{filteredResults.length !== 1 ? 's' : ''} found
          {minScore > 0 && (
            <span className="text-slate-500 ml-2">
              (showing results with score ≥ {minScore.toFixed(1)})
            </span>
          )}
        </div>
      </div>

      {/* Results List */}
      <div className="space-y-4">
        {filteredResults.map((result, index) => (
          <div
            key={result.id}
            className="animate-slide-up"
            style={{
              animation: `slideUp 0.3s ease-out ${index * 50}ms forwards`,
              opacity: 0,
            }}
          >
            <ResultCard
              result={result}
              query={query}
              onAskAbout={onAskAbout}
              onViewDocument={onViewDocument}
            />
          </div>
        ))}
      </div>

      {/* Animation Styles */}
      <style>{`
        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  );
};

export default ResultList;
```

---

## 6. SearchHistory.tsx

**Location:** `src/components/search/SearchHistory.tsx`

**Responsibilities:**
- Display recent searches when input is empty
- Click to re-run search
- Clear individual items or all history
- Show example queries/suggestions

```typescript
import React from 'react';
import { ClockIcon, TrashIcon, SearchIcon } from 'lucide-react';

interface SearchHistoryItem {
  query: string;
  namespaces: string[];
  resultCount: number;
  timestamp: number;
}

interface SearchHistoryProps {
  history: SearchHistoryItem[];
  onSelect: (item: SearchHistoryItem) => void;
  onClear?: (query?: string) => void;
}

const EXAMPLE_QUERIES = [
  'machine learning algorithms',
  'deployment strategies',
  'API documentation',
  'database optimization',
  'authentication',
];

export const SearchHistory: React.FC<SearchHistoryProps> = ({
  history,
  onSelect,
  onClear,
}) => {
  const formatTime = (timestamp: number): string => {
    const now = Date.now();
    const diff = now - timestamp;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;

    return new Date(timestamp).toLocaleDateString();
  };

  const recentSearches = history.slice(0, 10);

  return (
    <div className="space-y-8">
      {/* Recent Searches */}
      {recentSearches.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
              <ClockIcon className="w-5 h-5 text-slate-500" />
              Recent Searches
            </h2>
            {onClear && (
              <button
                onClick={() => onClear()}
                className="text-xs font-medium text-slate-600 hover:text-slate-900 flex items-center gap-1 transition-colors"
              >
                <TrashIcon className="w-3 h-3" />
                Clear all
              </button>
            )}
          </div>

          <div className="grid gap-2">
            {recentSearches.map((item, index) => (
              <button
                key={`${item.query}-${index}`}
                onClick={() => onSelect(item)}
                className="w-full text-left p-4 rounded-lg bg-white border border-slate-200 hover:border-slate-300 hover:shadow-md transition-all group"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-slate-900 truncate group-hover:text-blue-600 transition-colors">
                      {item.query}
                    </p>
                    <div className="flex items-center gap-2 mt-1 text-xs text-slate-600">
                      {item.namespaces.length > 0 && (
                        <span>{item.namespaces.join(', ')}</span>
                      )}
                      <span className="text-slate-500">•</span>
                      <span>{item.resultCount} results</span>
                      <span className="text-slate-500">•</span>
                      <span>{formatTime(item.timestamp)}</span>
                    </div>
                  </div>

                  {onClear && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onClear(item.query);
                      }}
                      className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded transition-colors flex-shrink-0"
                      aria-label="Remove from history"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Example Queries / Suggestions */}
      <div>
        <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2 mb-4">
          <SearchIcon className="w-5 h-5 text-slate-500" />
          Try searching for
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {EXAMPLE_QUERIES.map((query) => (
            <button
              key={query}
              onClick={() =>
                onSelect({
                  query,
                  namespaces: [],
                  resultCount: 0,
                  timestamp: Date.now(),
                })
              }
              className="p-4 rounded-lg bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 hover:from-blue-100 hover:to-indigo-100 transition-all group text-left"
            >
              <p className="font-medium text-slate-900 group-hover:text-blue-600 transition-colors">
                {query}
              </p>
              <p className="text-xs text-slate-600 mt-1">
                Common search topic
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Empty State */}
      {recentSearches.length === 0 && (
        <div className="text-center py-12">
          <SearchIcon className="w-16 h-16 text-slate-300 mx-auto mb-4" />
          <p className="text-slate-600 mb-8">
            Your search history is empty. Start by searching for any keywords or try one of the examples above.
          </p>
        </div>
      )}
    </div>
  );
};

export default SearchHistory;
```

---

## 7. Supporting Files

### Hooks: useSearch.ts

**Location:** `src/hooks/useSearch.ts`

```typescript
import { useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';

interface SearchQuery {
  query: string;
  namespace?: string;
  top_k?: number;
  filter?: {
    minScore?: number;
    dateRange?: string;
  };
}

interface SearchResult {
  id: string;
  score: number;
  source: string;
  chunk_index: number;
  text: string;
  created_at?: string;
}

interface SearchResponse {
  query: string;
  results: SearchResult[];
  namespace: string;
  total_results: number;
}

export const useSearch = () => {
  return useMutation<SearchResponse, Error, SearchQuery>({
    mutationFn: async (params) => {
      const response = await api.post('/api/query', {
        query: params.query,
        namespace: params.namespace,
        top_k: params.top_k || 20,
        filter: params.filter,
      });
      return response.data;
    },
  });
};
```

### Store: searchStore.ts

**Location:** `src/store/searchStore.ts`

```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SearchHistoryItem {
  query: string;
  namespaces: string[];
  resultCount: number;
  timestamp: number;
}

interface SearchStoreState {
  history: SearchHistoryItem[];
  minScore: number;
  addSearch: (item: Omit<SearchHistoryItem, 'timestamp'>) => void;
  clearHistory: (query?: string) => void;
  setMinScore: (score: number) => void;
}

export const useSearchStore = create<SearchStoreState>()(
  persist(
    (set) => ({
      history: [],
      minScore: 0,

      addSearch: (item) =>
        set((state) => {
          // Remove duplicate if it exists
          const filtered = state.history.filter((h) => h.query !== item.query);
          // Add new search to beginning, limit to 50 items
          return {
            history: [
              { ...item, timestamp: Date.now() },
              ...filtered,
            ].slice(0, 50),
          };
        }),

      clearHistory: (query?) =>
        set((state) => ({
          history: query
            ? state.history.filter((h) => h.query !== query)
            : [],
        })),

      setMinScore: (score) =>
        set({ minScore: Math.max(0, Math.min(1, score)) }),
    }),
    {
      name: 'search-store',
      version: 1,
    }
  )
);
```

### Utility: debounce.ts

**Location:** `src/utils/debounce.ts`

```typescript
export const debounce = <T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): ((...args: Parameters<T>) => void) => {
  let timeoutId: NodeJS.Timeout | null = null;

  return (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    timeoutId = setTimeout(() => {
      fn(...args);
      timeoutId = null;
    }, delay);
  };
};
```

---

## Implementation Checklist

- [ ] Create `/src/pages/SearchPage.tsx`
- [ ] Create `/src/components/search/SearchInput.tsx`
- [ ] Create `/src/components/search/FilterPanel.tsx`
- [ ] Create `/src/components/search/ResultCard.tsx`
- [ ] Create `/src/components/search/ResultList.tsx`
- [ ] Create `/src/components/search/SearchHistory.tsx`
- [ ] Create `/src/hooks/useSearch.ts`
- [ ] Create `/src/store/searchStore.ts`
- [ ] Create `/src/utils/debounce.ts`
- [ ] Add search route to router configuration
- [ ] Test keyboard shortcuts (Cmd+K)
- [ ] Test URL parameter serialization/deserialization
- [ ] Verify debouncing works (300ms)
- [ ] Test search history persistence
- [ ] Test score badge color-coding
- [ ] Test text highlighting in results
- [ ] Test filter chip removal
- [ ] Verify staggered animation timing
- [ ] Test empty state messages
- [ ] Test loading skeleton display
- [ ] Verify responsive design on mobile

---

## CSS/Tailwind Notes

- All components use Tailwind utility classes
- No additional CSS files needed (Tailwind configured)
- Animations via inline `@keyframes` or Tailwind animation utilities
- Color scheme: slate (neutral), blue (primary), green/amber (status)
- Responsive: `flex-wrap`, `grid-cols-1 sm:grid-cols-2`, mobile-first
- Focus states: `focus:outline-none focus:border-blue-500 focus:shadow-lg`
- Transitions: `transition-all duration-200` for smooth UX

---

## Integration Points

**Route Configuration:**
```typescript
import SearchPage from '@/pages/SearchPage';

export const routes = [
  { path: '/search', element: <SearchPage /> },
];
```

**Header Navigation (Update existing component):**
```typescript
<Link to="/search" className="...">Search</Link>
```

**Required Dependencies:**
- `@tanstack/react-query` (already installed)
- `zustand` (state management)
- `lucide-react` (icons)
- `react-router-dom` (routing)

---

## Performance Considerations

1. **Debouncing:** 300ms debounce on input prevents excessive API calls
2. **Lazy Loading:** ResultCard content expands on demand
3. **Virtual Scrolling:** Not needed for typical result counts (use for 100+ results)
4. **Caching:** React Query caches search results by query/params
5. **History Persistence:** Zustand persists to localStorage (limited to 50 items)

---

## Accessibility

- Keyboard navigation: Cmd+K to focus search
- ARIA labels on buttons
- Semantic HTML: `<button>`, `<label>`, proper heading hierarchy
- Color contrast: WCAG AA compliant
- Focus indicators: Clear blue borders on focus
- Screen reader support: Button labels, icon descriptions

---

## Future Enhancements

1. Advanced search syntax (AND, OR, NOT operators)
2. Search suggestions/autocomplete from ML models
3. Saved searches/filters
4. Search result export (PDF, CSV)
5. Full-text search highlighting in document viewer
6. Search analytics/trending topics
7. Collaborative search history across team

