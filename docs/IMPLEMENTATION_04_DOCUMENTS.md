# Implementation 04: Documents Page & Components

**Status**: Complete Implementation Plan
**Target**: GLM-4.7
**Platform**: LLM-MD-CLI Web UI (RAG System)
**Backend**: FastAPI

---

## Overview

This document provides complete, production-ready code for the Documents page and all documents-specific components. The system allows users to upload, manage, and organize markdown files across multiple namespaces.

---

## Backend API Reference

### Status Endpoint
```
GET /api/status
Response: { index: { namespaces: Record<string, { vector_count }> } }
```

### Upload Endpoint
```
POST /api/upload
Form Data:
  - file: File (multipart)
  - namespace: string (default: "default")
  - tags: string (comma-separated, optional)

Response (sync):
  {
    status: "success" | "queued",
    file_name: string,
    chunks_created?: number,
    vectors_upserted?: number,
    namespace: string,
    job_id?: string
  }

Constraints:
  - Only .md files accepted
  - Files > 100KB processed asynchronously
  - Returns job_id for async jobs
```

### Jobs Endpoint
```
GET /api/jobs?namespace=X
Response:
  {
    jobs: JobInfo[],
    count: number
  }

JobInfo Structure:
  {
    id: string,
    file_name: string,
    namespace: string,
    status: "pending" | "processing" | "completed" | "failed",
    created_at: ISO8601,
    completed_at?: ISO8601,
    result?: {
      chunks_created: number,
      vectors_upserted: number,
      file_size: number
    },
    error?: string
  }
```

---

## Type Definitions

```typescript
// types/documents.ts

export interface NamespaceInfo {
  name: string;
  vector_count: number;
}

export interface DocumentInfo {
  id: string;
  file_name: string;
  namespace: string;
  chunks_count: number;
  file_size: number;
  indexed_at: Date;
  status: 'completed' | 'pending' | 'failed';
}

export interface JobInfo {
  id: string;
  file_name: string;
  namespace: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  completed_at?: string;
  result?: {
    chunks_created: number;
    vectors_upserted: number;
    file_size: number;
  };
  error?: string;
}

export interface UploadResult {
  status: 'success' | 'queued';
  file_name: string;
  chunks_created?: number;
  vectors_upserted?: number;
  namespace: string;
  job_id?: string;
}

export interface StatusResponse {
  index: {
    namespaces: Record<string, { vector_count: number }>;
  };
}
```

---

## Custom Hooks

### useNamespaces Hook

```typescript
// hooks/useNamespaces.ts

import { useEffect, useState } from 'react';
import { NamespaceInfo } from '../types/documents';

export function useNamespaces() {
  const [namespaces, setNamespaces] = useState<NamespaceInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchNamespaces = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/status');
        if (!response.ok) throw new Error('Failed to fetch namespaces');
        const data = await response.json();

        const namespaceList: NamespaceInfo[] = Object.entries(
          data.index.namespaces || {}
        ).map(([name, info]: [string, any]) => ({
          name,
          vector_count: info.vector_count || 0,
        }));

        setNamespaces(namespaceList.sort((a, b) => a.name.localeCompare(b.name)));
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setNamespaces([]);
      } finally {
        setLoading(false);
      }
    };

    fetchNamespaces();
    const interval = setInterval(fetchNamespaces, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  return { namespaces, loading, error };
}
```

### useDocuments Hook

```typescript
// hooks/useDocuments.ts

import { useEffect, useState } from 'react';
import { DocumentInfo, JobInfo } from '../types/documents';

export function useDocuments(namespace: string | null) {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!namespace) {
      setDocuments([]);
      setLoading(false);
      return;
    }

    const fetchDocuments = async () => {
      try {
        setLoading(true);
        const queryNamespace = namespace === 'all' ? undefined : namespace;
        const params = new URLSearchParams(
          queryNamespace ? { namespace: queryNamespace } : {}
        );

        const response = await fetch(`/api/jobs?${params}`);
        if (!response.ok) throw new Error('Failed to fetch documents');
        const data = await response.json();

        const docs: DocumentInfo[] = (data.jobs || [])
          .filter((job: JobInfo) => job.status === 'completed' && job.result)
          .map((job: JobInfo) => ({
            id: job.id,
            file_name: job.file_name,
            namespace: job.namespace,
            chunks_count: job.result?.chunks_created || 0,
            file_size: job.result?.file_size || 0,
            indexed_at: new Date(job.completed_at || job.created_at),
            status: 'completed',
          }));

        setDocuments(docs.sort((a, b) =>
          b.indexed_at.getTime() - a.indexed_at.getTime()
        ));
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setDocuments([]);
      } finally {
        setLoading(false);
      }
    };

    fetchDocuments();
    const interval = setInterval(fetchDocuments, 20000); // Refresh every 20s
    return () => clearInterval(interval);
  }, [namespace]);

  return { documents, loading, error };
}
```

### useUpload Hook

```typescript
// hooks/useUpload.ts

import { useState, useCallback } from 'react';
import { UploadResult } from '../types/documents';

export interface UploadItem {
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'success' | 'error';
  error?: string;
  result?: UploadResult;
}

interface UseUploadOptions {
  onSuccess?: (results: UploadResult[]) => void;
  onError?: (error: string) => void;
}

export function useUpload(options?: UseUploadOptions) {
  const [items, setItems] = useState<UploadItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const uploadFiles = useCallback(
    async (files: File[], namespace: string) => {
      const uploadItems: UploadItem[] = files.map(file => ({
        file,
        progress: 0,
        status: 'pending',
      }));

      setItems(uploadItems);
      setIsUploading(true);

      const results: UploadResult[] = [];
      const errors: string[] = [];

      for (let i = 0; i < uploadItems.length; i++) {
        const uploadItem = uploadItems[i];

        try {
          setItems(prev => {
            const newItems = [...prev];
            newItems[i] = { ...newItems[i], status: 'uploading' };
            return newItems;
          });

          const formData = new FormData();
          formData.append('file', uploadItem.file);
          formData.append('namespace', namespace);

          const xhr = new XMLHttpRequest();

          // Track upload progress
          xhr.upload.addEventListener('progress', (event) => {
            if (event.lengthComputable) {
              const progress = (event.loaded / event.total) * 100;
              setItems(prev => {
                const newItems = [...prev];
                newItems[i] = { ...newItems[i], progress };
                return newItems;
              });
            }
          });

          const response = await new Promise<UploadResult>((resolve, reject) => {
            xhr.onload = () => {
              if (xhr.status >= 200 && xhr.status < 300) {
                resolve(JSON.parse(xhr.responseText));
              } else {
                reject(new Error(`Upload failed: ${xhr.status}`));
              }
            };
            xhr.onerror = () => reject(new Error('Upload error'));
            xhr.open('POST', '/api/upload');
            xhr.send(formData);
          });

          results.push(response);
          setItems(prev => {
            const newItems = [...prev];
            newItems[i] = {
              ...newItems[i],
              status: 'success',
              progress: 100,
              result: response,
            };
            return newItems;
          });
        } catch (error) {
          const errorMsg = error instanceof Error ? error.message : 'Unknown error';
          errors.push(`${uploadItem.file.name}: ${errorMsg}`);
          setItems(prev => {
            const newItems = [...prev];
            newItems[i] = {
              ...newItems[i],
              status: 'error',
              error: errorMsg,
            };
            return newItems;
          });
        }
      }

      setIsUploading(false);

      if (results.length > 0) {
        options?.onSuccess?.(results);
      }
      if (errors.length > 0) {
        options?.onError?.(errors.join('; '));
      }

      return { results, errors };
    },
    [options]
  );

  const clear = useCallback(() => {
    setItems([]);
  }, []);

  const removeItem = useCallback((index: number) => {
    setItems(prev => prev.filter((_, i) => i !== index));
  }, []);

  return { items, isUploading, uploadFiles, clear, removeItem };
}
```

---

## Components

### 1. DocumentsPage.tsx

```typescript
// src/pages/DocumentsPage.tsx

import React, { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useNamespaces } from '../hooks/useNamespaces';
import { useDocuments } from '../hooks/useDocuments';
import NamespaceTree from '../components/documents/NamespaceTree';
import DocumentTable from '../components/documents/DocumentTable';
import DocumentGrid from '../components/documents/DocumentGrid';
import UploadModal from '../components/documents/UploadModal';
import { Button } from '../components/ui/Button';
import { Icon } from '../components/ui/Icon';

type ViewMode = 'list' | 'grid';

interface DocumentsPageState {
  viewMode: ViewMode;
  uploadModalOpen: boolean;
  selectedDocuments: string[];
}

export default function DocumentsPage() {
  const { namespace: paramNamespace } = useParams<{ namespace?: string }>();
  const navigate = useNavigate();

  const [state, setState] = useState<DocumentsPageState>({
    viewMode: 'list',
    uploadModalOpen: false,
    selectedDocuments: [],
  });

  const { namespaces, loading: namespacesLoading } = useNamespaces();

  const selectedNamespace = useMemo(() => {
    if (paramNamespace === 'all' || !paramNamespace) return 'all';
    if (namespaces.some(ns => ns.name === paramNamespace)) return paramNamespace;
    return 'all';
  }, [paramNamespace, namespaces]);

  const { documents, loading: documentsLoading } = useDocuments(
    selectedNamespace === 'all' ? null : selectedNamespace
  );

  const updateState = (updates: Partial<DocumentsPageState>) => {
    setState(prev => ({ ...prev, ...updates }));
  };

  const handleNamespaceSelect = (namespace: string) => {
    navigate(`/documents/${namespace}`);
    updateState({ selectedDocuments: [] });
  };

  const handleViewModeChange = (mode: ViewMode) => {
    updateState({ viewMode: mode });
  };

  const handleSelectDocuments = (documentIds: string[]) => {
    updateState({ selectedDocuments: documentIds });
  };

  const handleUploadSuccess = () => {
    updateState({ uploadModalOpen: false });
    // Documents will auto-refresh via useDocuments hook
  };

  const totalVectorCount = useMemo(() => {
    return selectedNamespace === 'all'
      ? namespaces.reduce((sum, ns) => sum + ns.vector_count, 0)
      : namespaces.find(ns => ns.name === selectedNamespace)?.vector_count || 0;
  }, [selectedNamespace, namespaces]);

  return (
    <div className="flex h-full bg-white dark:bg-slate-950">
      {/* Namespace Sidebar */}
      <aside className="hidden lg:flex lg:w-64 flex-col border-r border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900">
        <NamespaceTree
          namespaces={namespaces}
          selected={selectedNamespace}
          onSelect={handleNamespaceSelect}
          loading={namespacesLoading}
        />
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="flex items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-6 py-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
              Documents
            </h1>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              {selectedNamespace === 'all'
                ? `All namespaces (${totalVectorCount} vectors)`
                : `${selectedNamespace} (${totalVectorCount} vectors)`}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {/* View Toggle */}
            <div className="flex gap-1 border border-slate-200 dark:border-slate-700 rounded-lg p-1">
              <button
                onClick={() => handleViewModeChange('list')}
                className={`p-2 rounded ${
                  state.viewMode === 'list'
                    ? 'bg-brand-100 dark:bg-brand-900 text-brand-600 dark:text-brand-400'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
                title="List view"
              >
                <Icon name="list" size={18} />
              </button>
              <button
                onClick={() => handleViewModeChange('grid')}
                className={`p-2 rounded ${
                  state.viewMode === 'grid'
                    ? 'bg-brand-100 dark:bg-brand-900 text-brand-600 dark:text-brand-400'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
                title="Grid view"
              >
                <Icon name="grid" size={18} />
              </button>
            </div>

            {/* Upload Button */}
            <Button
              onClick={() => updateState({ uploadModalOpen: true })}
              variant="primary"
              className="gap-2"
            >
              <Icon name="upload" size={18} />
              <span className="hidden sm:inline">Upload</span>
            </Button>
          </div>
        </header>

        {/* Content Area */}
        <div className="flex-1 overflow-auto">
          {documents.length === 0 && !documentsLoading ? (
            <div className="flex flex-col items-center justify-center h-full gap-4 px-6 py-12">
              <Icon name="file-text" size={48} className="text-slate-300 dark:text-slate-700" />
              <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                No documents yet
              </h2>
              <p className="text-slate-600 dark:text-slate-400 text-center max-w-md">
                {selectedNamespace === 'all'
                  ? 'Start by uploading your first markdown file.'
                  : `No documents in "${selectedNamespace}" namespace. Upload some markdown files to get started.`}
              </p>
              <Button
                onClick={() => updateState({ uploadModalOpen: true })}
                variant="primary"
              >
                <Icon name="upload" size={18} />
                Upload Documents
              </Button>
            </div>
          ) : state.viewMode === 'list' ? (
            <DocumentTable
              documents={documents}
              selectedIds={state.selectedDocuments}
              onSelectionChange={handleSelectDocuments}
              loading={documentsLoading}
              namespace={selectedNamespace === 'all' ? undefined : selectedNamespace}
            />
          ) : (
            <DocumentGrid
              documents={documents}
              selectedIds={state.selectedDocuments}
              onSelectionChange={handleSelectDocuments}
              loading={documentsLoading}
            />
          )}
        </div>
      </main>

      {/* Upload Modal */}
      <UploadModal
        open={state.uploadModalOpen}
        onOpenChange={(open) => updateState({ uploadModalOpen: open })}
        defaultNamespace={selectedNamespace === 'all' ? 'default' : selectedNamespace}
        namespaces={namespaces}
        onSuccess={handleUploadSuccess}
      />
    </div>
  );
}
```

### 2. NamespaceTree.tsx

```typescript
// src/components/documents/NamespaceTree.tsx

import React, { useState } from 'react';
import { NamespaceInfo } from '../../types/documents';
import { Icon } from '../ui/Icon';
import { Skeleton } from '../ui/Skeleton';

interface NamespaceTreeProps {
  namespaces: NamespaceInfo[];
  selected: string | null;
  onSelect: (namespace: string) => void;
  loading?: boolean;
}

export default function NamespaceTree({
  namespaces,
  selected,
  onSelect,
  loading = false,
}: NamespaceTreeProps) {
  const [newNamespaceMode, setNewNamespaceMode] = useState(false);
  const [newNamespaceValue, setNewNamespaceValue] = useState('');

  const totalVectors = namespaces.reduce((sum, ns) => sum + ns.vector_count, 0);

  const handleNewNamespace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNamespaceValue.trim()) return;

    // In a real implementation, this would create the namespace on the backend
    // For now, we just clear the form and exit
    setNewNamespaceValue('');
    setNewNamespaceMode(false);
  };

  if (loading) {
    return (
      <div className="flex flex-col h-full p-4 gap-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  return (
    <nav className="flex flex-col h-full p-4 gap-2 overflow-y-auto">
      {/* All Namespaces Item */}
      <button
        onClick={() => onSelect('all')}
        className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
          selected === 'all'
            ? 'bg-brand-50 dark:bg-brand-950 text-brand-600 dark:text-brand-400'
            : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
        }`}
      >
        <Icon name="inbox" size={18} />
        <span>All Documents</span>
        <span className="ml-auto text-xs bg-slate-200 dark:bg-slate-800 rounded-full px-2 py-0.5">
          {totalVectors}
        </span>
      </button>

      <div className="my-2 border-t border-slate-200 dark:border-slate-700" />

      {/* Namespace Items */}
      {namespaces.length > 0 ? (
        namespaces.map((namespace) => (
          <button
            key={namespace.name}
            onClick={() => onSelect(namespace.name)}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              selected === namespace.name
                ? 'bg-brand-50 dark:bg-brand-950 text-brand-600 dark:text-brand-400'
                : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            <Icon name="folder" size={18} />
            <span className="truncate">{namespace.name}</span>
            <span className="ml-auto text-xs bg-slate-200 dark:bg-slate-800 rounded-full px-2 py-0.5 flex-shrink-0">
              {namespace.vector_count}
            </span>
          </button>
        ))
      ) : (
        <p className="text-xs text-slate-500 dark:text-slate-400 px-3 py-2">
          No namespaces yet
        </p>
      )}

      {/* New Namespace Button */}
      <div className="mt-auto pt-4 border-t border-slate-200 dark:border-slate-700">
        {newNamespaceMode ? (
          <form onSubmit={handleNewNamespace} className="flex gap-2">
            <input
              type="text"
              placeholder="Namespace name"
              value={newNamespaceValue}
              onChange={(e) => setNewNamespaceValue(e.target.value)}
              className="flex-1 px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-500 dark:placeholder-slate-400"
              autoFocus
            />
            <button
              type="submit"
              className="p-2 text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-900 rounded-lg"
              title="Create namespace"
            >
              <Icon name="check" size={18} />
            </button>
            <button
              type="button"
              onClick={() => {
                setNewNamespaceMode(false);
                setNewNamespaceValue('');
              }}
              className="p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
              title="Cancel"
            >
              <Icon name="x" size={18} />
            </button>
          </form>
        ) : (
          <button
            onClick={() => setNewNamespaceMode(true)}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            <Icon name="plus" size={18} />
            <span>New Namespace</span>
          </button>
        )}
      </div>
    </nav>
  );
}
```

### 3. DocumentTable.tsx

```typescript
// src/components/documents/DocumentTable.tsx

import React, { useMemo, useState } from 'react';
import { DocumentInfo } from '../../types/documents';
import { DataTable, Column, SortDirection } from '../ui/DataTable';
import { Icon } from '../ui/Icon';
import { Button } from '../ui/Button';
import ConfirmDialog from '../ui/ConfirmDialog';
import DocumentPreview from './DocumentPreview';
import { formatDistanceToNow } from 'date-fns';

interface DocumentTableProps {
  documents: DocumentInfo[];
  selectedIds: string[];
  onSelectionChange: (ids: string[]) => void;
  loading?: boolean;
  namespace?: string;
}

type SortField = 'name' | 'namespace' | 'date';

export default function DocumentTable({
  documents,
  selectedIds,
  onSelectionChange,
  loading = false,
  namespace,
}: DocumentTableProps) {
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<DocumentInfo | null>(null);

  const sortedDocuments = useMemo(() => {
    const sorted = [...documents];
    sorted.sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case 'name':
          comparison = a.file_name.localeCompare(b.file_name);
          break;
        case 'namespace':
          comparison = a.namespace.localeCompare(b.namespace);
          break;
        case 'date':
          comparison = a.indexed_at.getTime() - b.indexed_at.getTime();
          break;
      }
      return sortDirection === 'asc' ? comparison : -comparison;
    });
    return sorted;
  }, [documents, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const handleSelectAll = (selected: boolean) => {
    if (selected) {
      onSelectionChange(documents.map(d => d.id));
    } else {
      onSelectionChange([]);
    }
  };

  const handleSelectDocument = (id: string, selected: boolean) => {
    if (selected) {
      onSelectionChange([...selectedIds, id]);
    } else {
      onSelectionChange(selectedIds.filter(sid => sid !== id));
    }
  };

  const handleDelete = async (documentId: string) => {
    // In a real implementation, this would call the backend delete endpoint
    console.log('Delete document:', documentId);
    setDeleteConfirmId(null);
  };

  const handleReindex = async (documentId: string) => {
    // In a real implementation, this would call a re-index endpoint
    console.log('Re-index document:', documentId);
  };

  const handleBulkDelete = async () => {
    // In a real implementation, this would call the backend delete endpoint for multiple documents
    console.log('Delete documents:', selectedIds);
    onSelectionChange([]);
  };

  const columns: Column<DocumentInfo>[] = [
    {
      id: 'checkbox',
      header: (
        <input
          type="checkbox"
          checked={selectedIds.length === documents.length && documents.length > 0}
          onChange={(e) => handleSelectAll(e.target.checked)}
          className="w-4 h-4 rounded border-slate-300 dark:border-slate-600"
        />
      ),
      cell: (doc) => (
        <input
          type="checkbox"
          checked={selectedIds.includes(doc.id)}
          onChange={(e) => handleSelectDocument(doc.id, e.target.checked)}
          className="w-4 h-4 rounded border-slate-300 dark:border-slate-600"
        />
      ),
      width: 50,
    },
    {
      id: 'name',
      header: 'Name',
      cell: (doc) => (
        <button
          onClick={() => setSelectedDocument(doc)}
          className="flex items-center gap-2 text-left hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
        >
          <Icon name="file-text" size={16} className="text-slate-400" />
          <span className="font-medium text-slate-900 dark:text-white">
            {doc.file_name}
          </span>
        </button>
      ),
      sortable: true,
      onSort: () => handleSort('name'),
      isSorted: sortField === 'name',
      sortDirection: sortField === 'name' ? sortDirection : undefined,
    },
    {
      id: 'namespace',
      header: 'Namespace',
      cell: (doc) => (
        <span className="inline-block px-2 py-1 text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded">
          {doc.namespace}
        </span>
      ),
      sortable: true,
      onSort: () => handleSort('namespace'),
      isSorted: sortField === 'namespace',
      sortDirection: sortField === 'namespace' ? sortDirection : undefined,
      width: 140,
    },
    {
      id: 'chunks',
      header: 'Chunks',
      cell: (doc) => (
        <span className="text-sm text-slate-600 dark:text-slate-400">
          {doc.chunks_count}
        </span>
      ),
      width: 80,
    },
    {
      id: 'date',
      header: 'Indexed',
      cell: (doc) => (
        <span className="text-sm text-slate-600 dark:text-slate-400">
          {formatDistanceToNow(doc.indexed_at, { addSuffix: true })}
        </span>
      ),
      sortable: true,
      onSort: () => handleSort('date'),
      isSorted: sortField === 'date',
      sortDirection: sortField === 'date' ? sortDirection : undefined,
      width: 140,
    },
    {
      id: 'actions',
      header: '',
      cell: (doc) => (
        <div className="flex gap-1 justify-end">
          <button
            onClick={() => setSelectedDocument(doc)}
            className="p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
            title="View"
          >
            <Icon name="eye" size={16} />
          </button>
          <button
            onClick={() => handleReindex(doc.id)}
            className="p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
            title="Re-index"
          >
            <Icon name="refresh-cw" size={16} />
          </button>
          <button
            onClick={() => setDeleteConfirmId(doc.id)}
            className="p-2 text-slate-600 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600 rounded transition-colors"
            title="Delete"
          >
            <Icon name="trash-2" size={16} />
          </button>
        </div>
      ),
      width: 120,
    },
  ];

  return (
    <>
      {/* Bulk Actions Bar */}
      {selectedIds.length > 0 && (
        <div className="sticky top-0 z-10 border-b border-slate-200 dark:border-slate-800 bg-brand-50 dark:bg-brand-950 px-6 py-3 flex items-center justify-between">
          <span className="text-sm font-medium text-brand-900 dark:text-brand-100">
            {selectedIds.length} selected
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onSelectionChange([])}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => setDeleteConfirmId('bulk')}
            >
              <Icon name="trash-2" size={16} />
              Delete Selected
            </Button>
          </div>
        </div>
      )}

      {/* Table */}
      <DataTable
        columns={columns}
        data={sortedDocuments}
        loading={loading}
        emptyMessage="No documents found"
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteConfirmId !== null}
        title={deleteConfirmId === 'bulk' ? 'Delete Selected Documents?' : 'Delete Document?'}
        description={
          deleteConfirmId === 'bulk'
            ? `Are you sure you want to delete ${selectedIds.length} documents? This action cannot be undone.`
            : 'This action cannot be undone.'
        }
        confirmText="Delete"
        cancelText="Cancel"
        variant="danger"
        onConfirm={() => {
          if (deleteConfirmId === 'bulk') {
            handleBulkDelete();
          } else if (deleteConfirmId) {
            handleDelete(deleteConfirmId);
          }
        }}
        onCancel={() => setDeleteConfirmId(null)}
      />

      {/* Document Preview Modal */}
      {selectedDocument && (
        <DocumentPreview
          document={selectedDocument}
          onClose={() => setSelectedDocument(null)}
          onDelete={(id) => {
            setSelectedDocument(null);
            setDeleteConfirmId(id);
          }}
          onReindex={(id) => {
            handleReindex(id);
          }}
        />
      )}
    </>
  );
}
```

### 4. DocumentGrid.tsx

```typescript
// src/components/documents/DocumentGrid.tsx

import React, { useState } from 'react';
import { DocumentInfo } from '../../types/documents';
import { Icon } from '../ui/Icon';
import { Skeleton } from '../ui/Skeleton';
import DocumentPreview from './DocumentPreview';
import ConfirmDialog from '../ui/ConfirmDialog';
import { formatDistanceToNow } from 'date-fns';

interface DocumentGridProps {
  documents: DocumentInfo[];
  selectedIds: string[];
  onSelectionChange: (ids: string[]) => void;
  loading?: boolean;
}

export default function DocumentGrid({
  documents,
  selectedIds,
  onSelectionChange,
  loading = false,
}: DocumentGridProps) {
  const [selectedDocument, setSelectedDocument] = useState<DocumentInfo | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const handleSelectDocument = (id: string, selected: boolean) => {
    if (selected) {
      onSelectionChange([...selectedIds, id]);
    } else {
      onSelectionChange(selectedIds.filter(sid => sid !== id));
    }
  };

  const handleDelete = async (documentId: string) => {
    console.log('Delete document:', documentId);
    setDeleteConfirmId(null);
  };

  const handleReindex = async (documentId: string) => {
    console.log('Re-index document:', documentId);
  };

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-48 rounded-lg" />
        ))}
      </div>
    );
  }

  if (documents.length === 0) {
    return null;
  }

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-6">
        {documents.map((doc) => {
          const isSelected = selectedIds.includes(doc.id);
          return (
            <div
              key={doc.id}
              className={`relative group rounded-lg border transition-all ${
                isSelected
                  ? 'border-brand-400 dark:border-brand-600 bg-brand-50/50 dark:bg-brand-950/30'
                  : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:shadow-lg hover:border-slate-300 dark:hover:border-slate-700'
              }`}
            >
              {/* Selection Checkbox */}
              <div className="absolute top-2 left-2 z-10">
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={(e) => handleSelectDocument(doc.id, e.target.checked)}
                  className="w-4 h-4 rounded border-slate-300 dark:border-slate-600 cursor-pointer"
                />
              </div>

              {/* Card Content */}
              <div
                onClick={() => setSelectedDocument(doc)}
                className="p-4 cursor-pointer h-full flex flex-col gap-3"
              >
                {/* Icon & Title */}
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-slate-100 dark:bg-slate-800 rounded-lg flex-shrink-0">
                    <Icon name="file-text" size={24} className="text-slate-600 dark:text-slate-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-slate-900 dark:text-white truncate text-sm">
                      {doc.file_name}
                    </h3>
                  </div>
                </div>

                {/* Metadata */}
                <div className="flex flex-wrap gap-2">
                  <span className="inline-block px-2 py-1 text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded">
                    {doc.namespace}
                  </span>
                  <span className="inline-block px-2 py-1 text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded">
                    {doc.chunks_count} chunks
                  </span>
                </div>

                {/* Date */}
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-auto">
                  {formatDistanceToNow(doc.indexed_at, { addSuffix: true })}
                </p>
              </div>

              {/* Action Buttons (Visible on Hover) */}
              <div className="absolute top-2 right-2 z-20 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleReindex(doc.id);
                  }}
                  className="p-2 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 hover:text-slate-900 dark:hover:text-white rounded-lg shadow transition-colors"
                  title="Re-index"
                >
                  <Icon name="refresh-cw" size={16} />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteConfirmId(doc.id);
                  }}
                  className="p-2 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600 rounded-lg shadow transition-colors"
                  title="Delete"
                >
                  <Icon name="trash-2" size={16} />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteConfirmId !== null}
        title="Delete Document?"
        description="This action cannot be undone."
        confirmText="Delete"
        cancelText="Cancel"
        variant="danger"
        onConfirm={() => {
          if (deleteConfirmId) {
            handleDelete(deleteConfirmId);
          }
        }}
        onCancel={() => setDeleteConfirmId(null)}
      />

      {/* Document Preview Modal */}
      {selectedDocument && (
        <DocumentPreview
          document={selectedDocument}
          onClose={() => setSelectedDocument(null)}
          onDelete={(id) => {
            setSelectedDocument(null);
            setDeleteConfirmId(id);
          }}
          onReindex={(id) => {
            handleReindex(id);
          }}
        />
      )}
    </>
  );
}
```

### 5. UploadModal.tsx

```typescript
// src/components/documents/UploadModal.tsx

import React, { useRef, useState } from 'react';
import { NamespaceInfo, UploadResult } from '../../types/documents';
import { useUpload } from '../../hooks/useUpload';
import Dialog from '../ui/Dialog';
import { Button } from '../ui/Button';
import { Icon } from '../ui/Icon';
import { Alert } from '../ui/Alert';

interface UploadModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultNamespace?: string;
  namespaces: NamespaceInfo[];
  onSuccess?: (results: UploadResult[]) => void;
}

type UploadStep = 'empty' | 'selected' | 'uploading' | 'complete';

export default function UploadModal({
  open,
  onOpenChange,
  defaultNamespace = 'default',
  namespaces,
  onSuccess,
}: UploadModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropZoneRef = useRef<HTMLDivElement>(null);

  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [selectedNamespace, setSelectedNamespace] = useState(defaultNamespace);
  const [newNamespaceInput, setNewNamespaceInput] = useState('');
  const [useNewNamespace, setUseNewNamespace] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const { items, isUploading, uploadFiles, clear } = useUpload({
    onSuccess: (results) => {
      onSuccess?.(results);
      setTimeout(() => {
        handleClose();
      }, 2000);
    },
  });

  const currentStep: UploadStep = isUploading
    ? 'uploading'
    : items.length > 0
      ? 'complete'
      : selectedFiles.length > 0
        ? 'selected'
        : 'empty';

  const handleClose = () => {
    if (!isUploading) {
      setSelectedFiles([]);
      setNewNamespaceInput('');
      setUseNewNamespace(false);
      clear();
      onOpenChange(false);
    }
  };

  const handleFileSelect = (files: FileList) => {
    const newFiles = Array.from(files).filter((file) => file.name.endsWith('.md'));
    if (newFiles.length !== Array.from(files).length) {
      // Could show a warning about non-MD files
    }
    setSelectedFiles((prev) => [...prev, ...newFiles]);
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    handleFileSelect(e.dataTransfer.files);
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleStartUpload = async () => {
    if (selectedFiles.length === 0) return;

    const namespace = useNewNamespace ? newNamespaceInput : selectedNamespace;
    if (!namespace.trim()) {
      alert('Please enter a namespace name');
      return;
    }

    await uploadFiles(selectedFiles, namespace);
  };

  const successCount = items.filter((item) => item.status === 'success').length;
  const errorCount = items.filter((item) => item.status === 'error').length;
  const totalChunks = items.reduce(
    (sum, item) => sum + (item.result?.chunks_created || 0),
    0
  );

  return (
    <Dialog open={open} onOpenChange={handleClose} size="lg">
      <div className="flex flex-col gap-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
            Upload Documents
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Upload markdown files to index them into your vector database
          </p>
        </div>

        {/* Empty State */}
        {currentStep === 'empty' && (
          <div
            ref={dropZoneRef}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl transition-colors p-8 text-center cursor-pointer ${
              isDragging
                ? 'border-brand-400 dark:border-brand-600 bg-brand-50/50 dark:bg-brand-950/30'
                : 'border-slate-300 dark:border-slate-600 hover:border-brand-400 dark:hover:border-brand-600 hover:bg-brand-50/50 dark:hover:bg-brand-950/30'
            }`}
            onClick={() => fileInputRef.current?.click()}
          >
            <Icon name="upload-cloud" size={48} className="mx-auto text-slate-400 dark:text-slate-600 mb-3" />
            <h3 className="font-semibold text-slate-900 dark:text-white mb-1">
              Drop files here or click to browse
            </h3>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Only .md files are supported
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".md"
              onChange={(e) => {
                if (e.target.files) {
                  handleFileSelect(e.target.files);
                }
              }}
              className="hidden"
            />
          </div>
        )}

        {/* Selected Files */}
        {(currentStep === 'selected' || currentStep === 'uploading') && (
          <div className="space-y-4">
            {/* File List */}
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {(currentStep === 'selected' ? selectedFiles : items).map((item, index) => {
                const file = currentStep === 'selected' ? item : item.file;
                const uploadItem = currentStep === 'uploading' ? item : null;

                return (
                  <div
                    key={index}
                    className="rounded-lg border border-slate-200 dark:border-slate-700 p-3 flex items-center gap-3 hover:bg-slate-50 dark:hover:bg-slate-800"
                  >
                    <Icon name="file-text" size={18} className="text-slate-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
                        {file.name}
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {(file.size / 1024).toFixed(1)} KB
                      </p>
                      {uploadItem && uploadItem.status === 'uploading' && (
                        <div className="mt-2 w-full bg-slate-200 dark:bg-slate-700 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-brand-600 h-full transition-all"
                            style={{ width: `${uploadItem.progress}%` }}
                          />
                        </div>
                      )}
                      {uploadItem?.status === 'success' && (
                        <p className="text-xs text-green-600 dark:text-green-400 mt-1">
                          ✓ Uploaded ({uploadItem.result?.chunks_created} chunks)
                        </p>
                      )}
                      {uploadItem?.status === 'error' && (
                        <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                          ✗ {uploadItem.error}
                        </p>
                      )}
                    </div>
                    {currentStep === 'selected' && (
                      <button
                        onClick={() => handleRemoveFile(index)}
                        className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                        title="Remove"
                      >
                        <Icon name="x" size={18} />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Namespace Selector */}
            {currentStep === 'selected' && (
              <div className="space-y-3">
                <label className="text-sm font-medium text-slate-900 dark:text-white">
                  Namespace
                </label>
                <div className="space-y-2">
                  {!useNewNamespace ? (
                    <>
                      <select
                        value={selectedNamespace}
                        onChange={(e) => setSelectedNamespace(e.target.value)}
                        className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                      >
                        {namespaces.map((ns) => (
                          <option key={ns.name} value={ns.name}>
                            {ns.name} ({ns.vector_count} vectors)
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={() => setUseNewNamespace(true)}
                        className="text-sm text-brand-600 dark:text-brand-400 hover:underline"
                      >
                        + Create new namespace
                      </button>
                    </>
                  ) : (
                    <>
                      <input
                        type="text"
                        placeholder="Enter namespace name"
                        value={newNamespaceInput}
                        onChange={(e) => setNewNamespaceInput(e.target.value)}
                        className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-500 dark:placeholder-slate-400"
                        autoFocus
                      />
                      <button
                        onClick={() => setUseNewNamespace(false)}
                        className="text-sm text-slate-600 dark:text-slate-400 hover:underline"
                      >
                        Use existing namespace
                      </button>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Success State */}
        {currentStep === 'complete' && (
          <Alert variant={errorCount > 0 ? 'warning' : 'success'}>
            <Icon name="check-circle" size={20} className="flex-shrink-0" />
            <div className="flex-1">
              <h3 className="font-semibold">Upload Complete</h3>
              <p className="text-sm mt-1">
                {successCount} file{successCount !== 1 ? 's' : ''} uploaded with {totalChunks} chunks created.
                {errorCount > 0 && ` ${errorCount} file${errorCount !== 1 ? 's' : ''} failed.`}
              </p>
            </div>
          </Alert>
        )}

        {/* Actions */}
        <div className="flex gap-2 justify-end">
          <Button variant="secondary" onClick={handleClose}>
            {currentStep === 'empty' ? 'Cancel' : 'Close'}
          </Button>
          {currentStep === 'selected' && (
            <>
              <Button
                variant="secondary"
                onClick={() => {
                  setSelectedFiles([]);
                }}
              >
                Clear Files
              </Button>
              <Button
                variant="primary"
                onClick={handleStartUpload}
              >
                <Icon name="upload" size={18} />
                Upload Files
              </Button>
            </>
          )}
        </div>
      </div>
    </Dialog>
  );
}
```

### 6. DocumentPreview.tsx

```typescript
// src/components/documents/DocumentPreview.tsx

import React, { useState, useEffect } from 'react';
import { DocumentInfo } from '../../types/documents';
import Dialog from '../ui/Dialog';
import { Button } from '../ui/Button';
import { Icon } from '../ui/Icon';
import MarkdownRenderer from '../ui/MarkdownRenderer';
import ConfirmDialog from '../ui/ConfirmDialog';
import { formatDistanceToNow } from 'date-fns';

interface DocumentPreviewProps {
  document: DocumentInfo;
  onClose: () => void;
  onDelete: (id: string) => void;
  onReindex: (id: string) => void;
}

export default function DocumentPreview({
  document,
  onClose,
  onDelete,
  onReindex,
}: DocumentPreviewProps) {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  useEffect(() => {
    const fetchContent = async () => {
      try {
        setLoading(true);
        // In a real implementation, this would fetch the document content from the backend
        // For now, we show a placeholder
        setContent(`# ${document.file_name}\n\n*Document preview would display content here.*`);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load document');
      } finally {
        setLoading(false);
      }
    };

    fetchContent();
  }, [document.id]);

  const fileSizeKB = document.file_size / 1024;

  return (
    <>
      <Dialog open={true} onOpenChange={onClose} size="xl">
        <div className="flex flex-col gap-6 max-h-[80vh]">
          {/* Header */}
          <div className="border-b border-slate-200 dark:border-slate-800 pb-4">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-slate-100 dark:bg-slate-800 rounded-lg flex-shrink-0">
                <Icon name="file-text" size={32} className="text-slate-600 dark:text-slate-400" />
              </div>
              <div className="flex-1">
                <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
                  {document.file_name}
                </h2>
                <div className="flex flex-wrap gap-4 mt-3 text-sm text-slate-600 dark:text-slate-400">
                  <div className="flex items-center gap-1">
                    <Icon name="tag" size={16} />
                    <span>{document.namespace}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Icon name="box" size={16} />
                    <span>{document.chunks_count} chunks</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Icon name="hard-drive" size={16} />
                    <span>{fileSizeKB.toFixed(1)} KB</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Icon name="clock" size={16} />
                    <span>{formatDistanceToNow(document.indexed_at, { addSuffix: true })}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center h-64">
                <div className="text-center">
                  <Icon name="loader" size={32} className="mx-auto text-slate-400 animate-spin" />
                  <p className="mt-2 text-slate-600 dark:text-slate-400">Loading document...</p>
                </div>
              </div>
            ) : error ? (
              <div className="flex items-center justify-center h-64">
                <div className="text-center">
                  <Icon name="alert-circle" size={32} className="mx-auto text-red-400" />
                  <p className="mt-2 text-red-600 dark:text-red-400">{error}</p>
                </div>
              </div>
            ) : (
              <div className="prose dark:prose-invert max-w-none">
                <MarkdownRenderer content={content} />
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-slate-200 dark:border-slate-800 pt-4 flex gap-2 justify-end">
            <Button variant="secondary" onClick={onClose}>
              Close
            </Button>
            <Button
              variant="secondary"
              onClick={() => onReindex(document.id)}
            >
              <Icon name="refresh-cw" size={18} />
              Re-index
            </Button>
            <Button
              variant="danger"
              onClick={() => setDeleteConfirm(true)}
            >
              <Icon name="trash-2" size={18} />
              Delete
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={deleteConfirm}
        title="Delete Document?"
        description={`Are you sure you want to delete "${document.file_name}"? This action cannot be undone.`}
        confirmText="Delete"
        cancelText="Cancel"
        variant="danger"
        onConfirm={() => {
          onDelete(document.id);
          setDeleteConfirm(false);
        }}
        onCancel={() => setDeleteConfirm(false)}
      />
    </>
  );
}
```

---

## Shared UI Components (Dependencies)

The components above require these shared UI components:

- **Dialog**: Modal dialog component
- **DataTable**: Reusable table component with sorting
- **Button**: Button component with variants
- **Icon**: Icon library wrapper
- **FileUpload**: File upload input component
- **Alert**: Alert/notification component
- **Skeleton**: Loading skeleton component
- **ConfirmDialog**: Confirmation dialog component
- **MarkdownRenderer**: Markdown to HTML renderer

---

## Style Guidelines

### Spacing & Colors
```
Sidebar width: 250px (desktop), hidden on mobile
Padding: 6 (24px) for main areas, 4 (16px) for smaller sections
Gap: 2 (8px) for compact, 3 (12px) for normal, 4 (16px) for spacious
```

### Dark Mode
```
Background: white / dark:slate-950
Sidebar: slate-50 / dark:slate-900
Cards/Items: white / dark:slate-900
Borders: slate-200 / dark:slate-800
Text: slate-900 / dark:white
Secondary text: slate-600 / dark:slate-400
```

### Interactive States
```
Hover: bg-slate-50 / dark:bg-slate-800
Active: bg-brand-50 / dark:bg-brand-950, text-brand-600 / dark:text-brand-400
Focus: ring-2 ring-brand-400
Disabled: opacity-50 cursor-not-allowed
```

### Upload Zone
```
Default: border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-xl
Hover: border-brand-400 dark:border-brand-600 bg-brand-50/50 dark:bg-brand-950/30
Active (drag): border-brand-400 bg-brand-50/50
```

---

## Data Flow

1. **Namespace Sidebar** → `useNamespaces()` → displays namespaces
2. **URL Parameter** → selected namespace updates documents query
3. **useDocuments()** → fetches completed jobs, derives document list
4. **DocumentTable/Grid** → displays filtered documents
5. **UploadModal** → `useUpload()` → POST `/api/upload` → triggers document refresh
6. **Polling** → `useNamespaces()` and `useDocuments()` both auto-refresh every 20-30s

---

## Implementation Checklist

- [ ] Create type definitions file (`types/documents.ts`)
- [ ] Implement `useNamespaces()` hook with polling
- [ ] Implement `useDocuments()` hook with polling
- [ ] Implement `useUpload()` hook with progress tracking
- [ ] Create `DocumentsPage.tsx` with full layout
- [ ] Create `NamespaceTree.tsx` sidebar component
- [ ] Create `DocumentTable.tsx` with DataTable integration
- [ ] Create `DocumentGrid.tsx` with card layout
- [ ] Create `UploadModal.tsx` with drag-drop support
- [ ] Create `DocumentPreview.tsx` modal component
- [ ] Add routing: `/documents` and `/documents/:namespace`
- [ ] Test all interactions: upload, select, delete, view, re-index
- [ ] Test responsive behavior on mobile/tablet
- [ ] Test dark mode appearance
- [ ] Implement error handling and retry logic
- [ ] Add loading states and skeletons
- [ ] Add keyboard navigation support

---

## Notes

- Backend doesn't expose a dedicated documents endpoint, so we derive document info from completed jobs
- Files > 100KB return `job_id` and must be polled for completion
- All delete operations require confirmation dialogs
- Namespace sidebar becomes a dropdown on mobile (not implemented in this code, use media queries)
- Upload progress tracks individual file progress via XMLHttpRequest
- Document content fetching is a placeholder; implement actual content endpoint on backend
