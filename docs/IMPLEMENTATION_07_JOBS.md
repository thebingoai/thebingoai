# IMPLEMENTATION_07: Jobs Monitoring Page

## Overview
Complete implementation plan for a comprehensive Jobs monitoring page with real-time status tracking, filtering, and detailed job information display.

## Backend APIs

### List Jobs
```
GET /api/jobs?namespace=X&limit=50&offset=0&status=pending|processing|completed|failed

Response:
{
  jobs: [
    {
      job_id: string,
      status: "pending" | "processing" | "completed" | "failed",
      file_name: string,
      namespace: string,
      created_at: ISO8601,
      started_at?: ISO8601,
      completed_at?: ISO8601,
      progress: number (0-100),
      chunks_total?: number,
      chunks_processed?: number,
      error?: string,
      result?: {
        file_path: string,
        chunk_count: number,
        token_count: number
      }
    }
  ],
  count: number,
  total: number
}
```

### Get Job Details
```
GET /api/jobs/{job_id}

Response:
{
  job_id: string,
  status: "pending" | "processing" | "completed" | "failed",
  file_name: string,
  namespace: string,
  created_at: ISO8601,
  started_at?: ISO8601,
  completed_at?: ISO8601,
  progress: number (0-100),
  chunks_total?: number,
  chunks_processed?: number,
  current_operation?: string,
  logs: [
    { timestamp: ISO8601, level: "info" | "warning" | "error", message: string }
  ],
  error?: string,
  result?: object
}
```

### Cancel Job
```
POST /api/jobs/{job_id}/cancel

Response: { success: boolean }
```

### Retry Job
```
POST /api/jobs/{job_id}/retry

Response: { job_id: string, status: "pending" }
```

---

## Components

### 1. JobsPage.tsx
**Path:** `src/pages/JobsPage.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { JobsTable } from '@/components/jobs/JobsTable';
import { JobFilters } from '@/components/jobs/JobFilters';
import { JobDetailModal } from '@/components/jobs/JobDetailModal';
import { useJobs } from '@/hooks/useJobs';
import { JobStatus, JobInfo } from '@/types/job';
import { Loader2 } from 'lucide-react';

interface JobFiltersState {
  status?: JobStatus;
  timeRange?: 'all' | '1h' | '24h' | '7d';
  search?: string;
}

export function JobsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<JobFiltersState>({
    status: (searchParams.get('status') as JobStatus) || undefined,
    timeRange: (searchParams.get('timeRange') as any) || 'all',
    search: searchParams.get('search') || undefined,
  });
  const [page, setPage] = useState(parseInt(searchParams.get('page') || '1'));
  const [pageSize] = useState(10);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(
    searchParams.get('jobId')
  );
  const [autoRefresh, setAutoRefresh] = useState(true);

  const { jobs, isLoading, error, total } = useJobs(
    {
      status: filters.status,
      timeRange: filters.timeRange,
      search: filters.search,
    },
    {
      page,
      pageSize,
      autoRefresh,
      pollInterval: 5000,
    }
  );

  // Update URL when filters change
  useEffect(() => {
    const params = new URLSearchParams();
    if (filters.status) params.set('status', filters.status);
    if (filters.timeRange !== 'all') params.set('timeRange', filters.timeRange);
    if (filters.search) params.set('search', filters.search);
    params.set('page', page.toString());
    setSearchParams(params);
  }, [filters, page, setSearchParams]);

  const handleFilterChange = (newFilters: JobFiltersState) => {
    setFilters(newFilters);
    setPage(1);
  };

  const handleClearFilters = () => {
    setFilters({ timeRange: 'all' });
    setPage(1);
  };

  const totalPages = Math.ceil((total || 0) / pageSize);

  return (
    <div className="flex-1 overflow-auto">
      <div className="sticky top-0 z-10 bg-white dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800">
        <div className="px-6 py-4">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Jobs
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Monitor and manage document processing jobs
          </p>
        </div>
      </div>

      <div className="p-6">
        <JobFilters
          filters={filters}
          onFiltersChange={handleFilterChange}
          onClearFilters={handleClearFilters}
          autoRefresh={autoRefresh}
          onAutoRefreshChange={setAutoRefresh}
        />

        {error && (
          <div className="mt-4 p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-sm text-red-800 dark:text-red-200">
              {error.message || 'Failed to load jobs'}
            </p>
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-slate-400 animate-spin" />
            <span className="ml-2 text-slate-600 dark:text-slate-400">
              Loading jobs...
            </span>
          </div>
        ) : (
          <>
            <JobsTable
              jobs={jobs}
              onJobClick={setSelectedJobId}
              isLoading={isLoading}
            />

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-6 flex items-center justify-between">
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  Showing {(page - 1) * pageSize + 1} to{' '}
                  {Math.min(page * pageSize, total || 0)} of {total || 0} jobs
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(Math.max(1, page - 1))}
                    disabled={page === 1}
                    className="px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <div className="flex items-center px-3 py-2">
                    <span className="text-sm text-slate-600 dark:text-slate-400">
                      Page {page} of {totalPages}
                    </span>
                  </div>
                  <button
                    onClick={() => setPage(Math.min(totalPages, page + 1))}
                    disabled={page === totalPages}
                    className="px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {selectedJobId && (
        <JobDetailModal
          jobId={selectedJobId}
          onClose={() => setSelectedJobId(null)}
        />
      )}
    </div>
  );
}
```

---

### 2. JobsTable.tsx
**Path:** `src/components/jobs/JobsTable.tsx`

```typescript
import React, { useState } from 'react';
import { JobInfo, JobStatus } from '@/types/job';
import { JobStatusBadge } from './JobStatusBadge';
import { JobRow } from './JobRow';
import { DataTable } from '@/components/shared/DataTable';
import { formatDistanceToNow } from 'date-fns';
import { ChevronDown } from 'lucide-react';

interface JobsTableProps {
  jobs: JobInfo[];
  onJobClick: (jobId: string) => void;
  isLoading?: boolean;
}

type SortField = 'status' | 'type' | 'file_name' | 'progress' | 'created_at';
type SortOrder = 'asc' | 'desc';

export function JobsTable({ jobs, onJobClick, isLoading = false }: JobsTableProps) {
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  const getSortedJobs = () => {
    const sorted = [...jobs].sort((a, b) => {
      let aVal: any = a[sortField];
      let bVal: any = b[sortField];

      if (sortField === 'created_at') {
        aVal = new Date(a.created_at).getTime();
        bVal = new Date(b.created_at).getTime();
      } else if (sortField === 'progress') {
        aVal = a.progress || 0;
        bVal = b.progress || 0;
      }

      if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });

    return sorted;
  };

  const sortedJobs = getSortedJobs();

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <span className="opacity-0 group-hover:opacity-50">⬍</span>;
    }
    return <span>{sortOrder === 'asc' ? '⬆' : '⬇'}</span>;
  };

  // Mobile view
  if (typeof window !== 'undefined' && window.innerWidth < 768) {
    return (
      <div className="space-y-3">
        {sortedJobs.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-slate-500 dark:text-slate-400">
              {isLoading ? 'Loading jobs...' : 'No jobs found'}
            </p>
          </div>
        ) : (
          sortedJobs.map((job) => (
            <JobRow key={job.job_id} job={job} onClick={() => onJobClick(job.job_id)} />
          ))
        )}
      </div>
    );
  }

  // Desktop view - Table
  return (
    <div className="mt-6 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900">
            <th className="px-6 py-3 text-left">
              <button
                onClick={() => handleSort('status')}
                className="group inline-flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
              >
                Status {renderSortIcon('status')}
              </button>
            </th>
            <th className="px-6 py-3 text-left">
              <button
                onClick={() => handleSort('type')}
                className="group inline-flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
              >
                Type {renderSortIcon('type')}
              </button>
            </th>
            <th className="px-6 py-3 text-left">
              <button
                onClick={() => handleSort('file_name')}
                className="group inline-flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
              >
                File Name {renderSortIcon('file_name')}
              </button>
            </th>
            <th className="px-6 py-3 text-left">
              <button
                onClick={() => handleSort('progress')}
                className="group inline-flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
              >
                Progress {renderSortIcon('progress')}
              </button>
            </th>
            <th className="px-6 py-3 text-left">
              <button
                onClick={() => handleSort('created_at')}
                className="group inline-flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
              >
                Time {renderSortIcon('created_at')}
              </button>
            </th>
            <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 dark:text-slate-400">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedJobs.length === 0 ? (
            <tr>
              <td colSpan={6} className="px-6 py-12 text-center">
                <p className="text-slate-500 dark:text-slate-400">
                  {isLoading ? 'Loading jobs...' : 'No jobs found'}
                </p>
              </td>
            </tr>
          ) : (
            sortedJobs.map((job, idx) => (
              <tr
                key={job.job_id}
                className="border-b border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors"
              >
                <td className="px-6 py-4">
                  <JobStatusBadge status={job.status} />
                </td>
                <td className="px-6 py-4 text-sm text-slate-700 dark:text-slate-300">
                  {job.type || 'indexing'}
                </td>
                <td className="px-6 py-4 text-sm text-slate-700 dark:text-slate-300 max-w-xs truncate">
                  {job.file_name}
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          job.status === 'completed'
                            ? 'bg-green-500'
                            : job.status === 'failed'
                            ? 'bg-red-500'
                            : 'bg-blue-500'
                        }`}
                        style={{ width: `${job.progress || 0}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium text-slate-600 dark:text-slate-400 w-10 text-right">
                      {job.progress || 0}%
                    </span>
                  </div>
                  {job.chunks_processed !== undefined && (
                    <p className="text-xs text-slate-500 dark:text-slate-500 mt-1">
                      {job.chunks_processed}/{job.chunks_total || '?'} chunks
                    </p>
                  )}
                </td>
                <td className="px-6 py-4 text-sm text-slate-600 dark:text-slate-400">
                  {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
                </td>
                <td className="px-6 py-4">
                  <button
                    onClick={() => onJobClick(job.job_id)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors"
                  >
                    View
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
```

---

### 3. JobRow.tsx
**Path:** `src/components/jobs/JobRow.tsx`

```typescript
import React, { useState } from 'react';
import { JobInfo } from '@/types/job';
import { JobStatusBadge } from './JobStatusBadge';
import { formatDistanceToNow } from 'date-fns';
import { MoreVertical, Trash2, RotateCw } from 'lucide-react';

interface JobRowProps {
  job: JobInfo;
  onClick: () => void;
}

export function JobRow({ job, onClick }: JobRowProps) {
  const [showActions, setShowActions] = useState(false);

  return (
    <div
      className="p-4 border border-slate-200 dark:border-slate-800 rounded-lg bg-white dark:bg-slate-950 cursor-pointer hover:border-slate-300 dark:hover:border-slate-700 transition-colors"
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 flex-1">
          <JobStatusBadge status={job.status} />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
              {job.file_name}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              {job.type || 'indexing'}
            </p>
          </div>
        </div>

        <div className="relative" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => setShowActions(!showActions)}
            className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
          >
            <MoreVertical className="w-4 h-4 text-slate-500" />
          </button>

          {showActions && (
            <div className="absolute right-0 top-full mt-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg z-10">
              {job.status === 'failed' && (
                <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 first:rounded-t-lg">
                  <RotateCw className="w-4 h-4" />
                  Retry
                </button>
              )}
              {(job.status === 'pending' || job.status === 'processing') && (
                <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 last:rounded-b-lg">
                  <Trash2 className="w-4 h-4" />
                  Cancel
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <div className="flex-1 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                job.status === 'completed'
                  ? 'bg-green-500'
                  : job.status === 'failed'
                  ? 'bg-red-500'
                  : 'bg-blue-500'
              }`}
              style={{ width: `${job.progress || 0}%` }}
            />
          </div>
          <span className="text-xs font-medium text-slate-600 dark:text-slate-400 w-10 text-right">
            {job.progress || 0}%
          </span>
        </div>

        {job.chunks_processed !== undefined && (
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {job.chunks_processed}/{job.chunks_total || '?'} chunks
          </p>
        )}

        <p className="text-xs text-slate-500 dark:text-slate-400">
          {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
        </p>
      </div>
    </div>
  );
}
```

---

### 4. JobStatusBadge.tsx
**Path:** `src/components/jobs/JobStatusBadge.tsx`

```typescript
import React from 'react';
import { JobStatus } from '@/types/job';
import { Clock, Loader2, CheckCircle2, XCircle } from 'lucide-react';

interface JobStatusBadgeProps {
  status: JobStatus;
}

export function JobStatusBadge({ status }: JobStatusBadgeProps) {
  const getStatusConfig = (status: JobStatus) => {
    switch (status) {
      case 'pending':
        return {
          bg: 'bg-gray-100 dark:bg-gray-800',
          text: 'text-gray-700 dark:text-gray-300',
          icon: Clock,
          label: 'Pending',
        };
      case 'processing':
        return {
          bg: 'bg-blue-100 dark:bg-blue-900/30',
          text: 'text-blue-700 dark:text-blue-300',
          icon: Loader2,
          label: 'Processing',
          animate: true,
        };
      case 'completed':
        return {
          bg: 'bg-green-100 dark:bg-green-900/30',
          text: 'text-green-700 dark:text-green-300',
          icon: CheckCircle2,
          label: 'Completed',
        };
      case 'failed':
        return {
          bg: 'bg-red-100 dark:bg-red-900/30',
          text: 'text-red-700 dark:text-red-300',
          icon: XCircle,
          label: 'Failed',
        };
    }
  };

  const config = getStatusConfig(status);
  const Icon = config.icon;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.bg} ${config.text}`}
    >
      <Icon className={`w-3.5 h-3.5 ${config.animate ? 'animate-spin' : ''}`} />
      {config.label}
    </span>
  );
}
```

---

### 5. JobDetailModal.tsx
**Path:** `src/components/jobs/JobDetailModal.tsx`

```typescript
import React, { useEffect, useRef } from 'react';
import { JobInfo } from '@/types/job';
import { useJob } from '@/hooks/useJob';
import { JobStatusBadge } from './JobStatusBadge';
import { Dialog } from '@/components/shared/Dialog';
import { formatDistanceToNow, format } from 'date-fns';
import { Loader2, X, RotateCw, Trash2, Copy, Check } from 'lucide-react';
import { useState } from 'react';

interface JobDetailModalProps {
  jobId: string;
  onClose: () => void;
}

export function JobDetailModal({ jobId, onClose }: JobDetailModalProps) {
  const { job, isLoading, error, refetch } = useJob(jobId, {
    pollInterval: 2000,
  });
  const logsEndRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [isCanceling, setIsCanceling] = useState(false);

  // Auto-scroll logs to bottom
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [job?.logs]);

  const handleRetry = async () => {
    setIsRetrying(true);
    try {
      await fetch(`/api/jobs/${jobId}/retry`, { method: 'POST' });
      refetch();
    } finally {
      setIsRetrying(false);
    }
  };

  const handleCancel = async () => {
    setIsCanceling(true);
    try {
      await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
      refetch();
    } finally {
      setIsCanceling(false);
    }
  };

  const handleCopyJobId = () => {
    navigator.clipboard.writeText(jobId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isLoading && !job) {
    return (
      <Dialog open={true} onOpenChange={onClose} title="Job Details">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 text-slate-400 animate-spin" />
          <span className="ml-2 text-slate-600 dark:text-slate-400">
            Loading job details...
          </span>
        </div>
      </Dialog>
    );
  }

  if (error || !job) {
    return (
      <Dialog open={true} onOpenChange={onClose} title="Job Details">
        <div className="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-sm text-red-800 dark:text-red-200">
            {error?.message || 'Failed to load job details'}
          </p>
        </div>
      </Dialog>
    );
  }

  return (
    <Dialog open={true} onOpenChange={onClose} title="Job Details" size="lg">
      <div className="space-y-6">
        {/* Job Info Section */}
        <div className="space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                {job.file_name}
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                {job.namespace}
              </p>
            </div>
            <JobStatusBadge status={job.status} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                Job ID
              </p>
              <button
                onClick={handleCopyJobId}
                className="flex items-center gap-2 mt-1 text-sm font-mono text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white"
              >
                <span className="truncate">{jobId.substring(0, 12)}...</span>
                {copied ? (
                  <Check className="w-4 h-4 text-green-600" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </button>
            </div>

            <div>
              <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                Created
              </p>
              <p className="mt-1 text-sm text-slate-700 dark:text-slate-300">
                {format(new Date(job.created_at), 'MMM dd, yyyy HH:mm:ss')}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
              </p>
            </div>

            {job.started_at && (
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                  Started
                </p>
                <p className="mt-1 text-sm text-slate-700 dark:text-slate-300">
                  {format(new Date(job.started_at), 'MMM dd, yyyy HH:mm:ss')}
                </p>
              </div>
            )}

            {job.completed_at && (
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                  Completed
                </p>
                <p className="mt-1 text-sm text-slate-700 dark:text-slate-300">
                  {format(new Date(job.completed_at), 'MMM dd, yyyy HH:mm:ss')}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Progress Section */}
        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
            Progress
          </p>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-3 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  job.status === 'completed'
                    ? 'bg-green-500'
                    : job.status === 'failed'
                    ? 'bg-red-500'
                    : 'bg-blue-500'
                }`}
                style={{ width: `${job.progress || 0}%` }}
              />
            </div>
            <span className="text-sm font-semibold text-slate-700 dark:text-slate-300 w-12 text-right">
              {job.progress || 0}%
            </span>
          </div>

          {job.chunks_processed !== undefined && (
            <p className="text-sm text-slate-600 dark:text-slate-400">
              {job.chunks_processed} / {job.chunks_total || '?'} chunks processed
            </p>
          )}
        </div>

        {/* Current Operation */}
        {job.current_operation && (
          <div className="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
            <p className="text-xs text-blue-700 dark:text-blue-300 uppercase font-semibold tracking-wide">
              Current Operation
            </p>
            <p className="text-sm text-blue-900 dark:text-blue-100 mt-1">
              {job.current_operation}
            </p>
          </div>
        )}

        {/* Error Display */}
        {job.error && (
          <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-xs text-red-700 dark:text-red-300 uppercase font-semibold tracking-wide">
              Error
            </p>
            <p className="text-sm text-red-900 dark:text-red-100 mt-1 font-mono">
              {job.error}
            </p>
          </div>
        )}

        {/* Logs Section */}
        {job.logs && job.logs.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Logs
            </p>
            <div className="h-48 bg-slate-900 dark:bg-slate-950 border border-slate-700 rounded-lg p-3 overflow-y-auto font-mono text-xs">
              {job.logs.map((log, idx) => (
                <div
                  key={idx}
                  className={`${
                    log.level === 'error'
                      ? 'text-red-400'
                      : log.level === 'warning'
                      ? 'text-yellow-400'
                      : 'text-green-400'
                  } whitespace-pre-wrap break-words`}
                >
                  <span className="text-slate-500">
                    {format(new Date(log.timestamp), 'HH:mm:ss')}
                  </span>{' '}
                  [{log.level.toUpperCase()}] {log.message}
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-2 justify-end pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
          >
            Close
          </button>

          {job.status === 'failed' && (
            <button
              onClick={handleRetry}
              disabled={isRetrying}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 border border-blue-300 dark:border-blue-700 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/20 disabled:opacity-50 transition-colors"
            >
              {isRetrying ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <RotateCw className="w-4 h-4" />
              )}
              Retry
            </button>
          )}

          {(job.status === 'pending' || job.status === 'processing') && (
            <button
              onClick={handleCancel}
              disabled={isCanceling}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 dark:text-red-400 border border-red-300 dark:border-red-700 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50 transition-colors"
            >
              {isCanceling ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
              Cancel
            </button>
          )}
        </div>
      </div>
    </Dialog>
  );
}
```

---

### 6. JobFilters.tsx
**Path:** `src/components/jobs/JobFilters.tsx`

```typescript
import React from 'react';
import { JobStatus } from '@/types/job';
import { X, RefreshCw } from 'lucide-react';

interface JobFiltersState {
  status?: JobStatus;
  timeRange?: 'all' | '1h' | '24h' | '7d';
  search?: string;
}

interface JobFiltersProps {
  filters: JobFiltersState;
  onFiltersChange: (filters: JobFiltersState) => void;
  onClearFilters: () => void;
  autoRefresh: boolean;
  onAutoRefreshChange: (enabled: boolean) => void;
}

const STATUS_OPTIONS: { value: JobStatus | undefined; label: string }[] = [
  { value: undefined, label: 'All Status' },
  { value: 'pending', label: 'Pending' },
  { value: 'processing', label: 'Processing' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
];

const TIME_RANGE_OPTIONS: { value: 'all' | '1h' | '24h' | '7d'; label: string }[] = [
  { value: 'all', label: 'All Time' },
  { value: '1h', label: 'Last Hour' },
  { value: '24h', label: 'Last 24 Hours' },
  { value: '7d', label: 'Last 7 Days' },
];

export function JobFilters({
  filters,
  onFiltersChange,
  onClearFilters,
  autoRefresh,
  onAutoRefreshChange,
}: JobFiltersProps) {
  const hasActiveFilters = filters.status || filters.search || filters.timeRange !== 'all';

  return (
    <div className="space-y-4">
      <div className="flex flex-col md:flex-row gap-4 items-start md:items-center">
        {/* Search */}
        <div className="flex-1 min-w-0">
          <input
            type="text"
            placeholder="Search jobs by file name..."
            value={filters.search || ''}
            onChange={(e) =>
              onFiltersChange({ ...filters, search: e.target.value || undefined })
            }
            className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-500 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Status Filter */}
        <select
          value={filters.status || ''}
          onChange={(e) =>
            onFiltersChange({
              ...filters,
              status: (e.target.value as JobStatus) || undefined,
            })
          }
          className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value || ''}>
              {option.label}
            </option>
          ))}
        </select>

        {/* Time Range Filter */}
        <select
          value={filters.timeRange || 'all'}
          onChange={(e) =>
            onFiltersChange({
              ...filters,
              timeRange: e.target.value as any,
            })
          }
          className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {TIME_RANGE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        {/* Auto Refresh Toggle */}
        <label className="inline-flex items-center gap-2 px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => onAutoRefreshChange(e.target.checked)}
            className="rounded"
          />
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
            Auto-refresh
          </span>
        </label>

        {/* Clear Filters */}
        {hasActiveFilters && (
          <button
            onClick={onClearFilters}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
            Clear
          </button>
        )}
      </div>

      {/* Active Filters Badge */}
      {hasActiveFilters && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-600 dark:text-slate-400">Active filters:</span>
          <div className="flex gap-2 flex-wrap">
            {filters.status && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full text-xs font-medium">
                {filters.status}
                <button
                  onClick={() => onFiltersChange({ ...filters, status: undefined })}
                  className="hover:text-blue-900 dark:hover:text-blue-100"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}
            {filters.timeRange && filters.timeRange !== 'all' && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full text-xs font-medium">
                {filters.timeRange === '1h'
                  ? 'Last Hour'
                  : filters.timeRange === '24h'
                  ? 'Last 24h'
                  : 'Last 7d'}
                <button
                  onClick={() => onFiltersChange({ ...filters, timeRange: 'all' })}
                  className="hover:text-blue-900 dark:hover:text-blue-100"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}
            {filters.search && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full text-xs font-medium">
                "{filters.search}"
                <button
                  onClick={() => onFiltersChange({ ...filters, search: undefined })}
                  className="hover:text-blue-900 dark:hover:text-blue-100"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
```

---

## Type Definitions

### `src/types/job.ts`

```typescript
export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface JobInfo {
  job_id: string;
  status: JobStatus;
  file_name: string;
  namespace: string;
  type?: string;
  created_at: string; // ISO8601
  started_at?: string;
  completed_at?: string;
  progress: number; // 0-100
  chunks_total?: number;
  chunks_processed?: number;
  current_operation?: string;
  logs?: JobLog[];
  error?: string;
  result?: {
    file_path: string;
    chunk_count: number;
    token_count: number;
  };
}

export interface JobLog {
  timestamp: string; // ISO8601
  level: 'info' | 'warning' | 'error';
  message: string;
}

export interface JobsListResponse {
  jobs: JobInfo[];
  count: number;
  total: number;
}
```

---

## Hooks

### `src/hooks/useJobs.ts`

```typescript
import { useEffect, useState, useCallback } from 'react';
import { JobInfo, JobsListResponse, JobStatus } from '@/types/job';

interface UseJobsOptions {
  page?: number;
  pageSize?: number;
  autoRefresh?: boolean;
  pollInterval?: number;
}

interface UseJobsFilters {
  status?: JobStatus;
  timeRange?: 'all' | '1h' | '24h' | '7d';
  search?: string;
}

export function useJobs(filters: UseJobsFilters, options: UseJobsOptions = {}) {
  const {
    page = 1,
    pageSize = 10,
    autoRefresh = true,
    pollInterval = 5000,
  } = options;

  const [jobs, setJobs] = useState<JobInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      setError(null);
      const params = new URLSearchParams({
        limit: pageSize.toString(),
        offset: ((page - 1) * pageSize).toString(),
      });

      if (filters.status) params.append('status', filters.status);
      if (filters.search) params.append('search', filters.search);
      if (filters.timeRange && filters.timeRange !== 'all') {
        params.append('time_range', filters.timeRange);
      }

      const response = await fetch(`/api/jobs?${params}`);
      if (!response.ok) throw new Error('Failed to fetch jobs');

      const data: JobsListResponse = await response.json();
      setJobs(data.jobs);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, filters]);

  useEffect(() => {
    fetchJobs();

    if (!autoRefresh) return;

    const interval = setInterval(fetchJobs, pollInterval);
    return () => clearInterval(interval);
  }, [fetchJobs, autoRefresh, pollInterval]);

  return { jobs, total, isLoading, error, refetch: fetchJobs };
}
```

### `src/hooks/useJob.ts`

```typescript
import { useEffect, useState, useCallback } from 'react';
import { JobInfo } from '@/types/job';

interface UseJobOptions {
  pollInterval?: number;
}

export function useJob(jobId: string, options: UseJobOptions = {}) {
  const { pollInterval = 2000 } = options;

  const [job, setJob] = useState<JobInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchJob = useCallback(async () => {
    try {
      setError(null);
      const response = await fetch(`/api/jobs/${jobId}`);
      if (!response.ok) throw new Error('Failed to fetch job');

      const data: JobInfo = await response.json();
      setJob(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    fetchJob();

    const interval = setInterval(fetchJob, pollInterval);
    return () => clearInterval(interval);
  }, [fetchJob, pollInterval]);

  return { job, isLoading, error, refetch: fetchJob };
}
```

---

## Styling Notes

- Use Tailwind CSS utility classes
- Dark mode support via `dark:` prefix
- Responsive design: mobile-first approach
- Status badges use contextual colors: gray (pending), blue (processing), green (completed), red (failed)
- Smooth transitions on all interactive elements
- Loading states with spinner animations
- Auto-scrolling logs section with fixed height
- Relative timestamps for better UX (e.g., "5 minutes ago")
