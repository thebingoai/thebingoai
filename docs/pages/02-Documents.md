# Documents Page

**Route:** `/documents` or `/documents/:namespace`  
**Purpose:** Manage uploaded documents and namespaces  
**Priority:** P0

---

## Wireframe - List View

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LLM-MD-CLI                              [🔍 Search...]    [🌙]    [⚙️]   │
├──────────┬──────────────────────────────────────────────────────────────────┤
│          │  Documents                                     [⬆️ Upload] [≡] │
│  📊      │                                                                  │
│  📄 Docs │  ┌──────────────┬───────────────────────────────────────────────┤
│  🔍 Search│  │ Namespaces   │  Documents (23 files)                         │
│  💬 Chat │  │              │  ┌───────────────────────────────────────────┐│
│  ⚙️ Jobs │  │  📁 All (23) │  │ [🔍 Filter documents...          ] [⚙️] ││
│  ⚙️ Settings│  │  📁 personal │  ├───────────────────────────────────────────┤│
│          │  │     (12)     │  │ □ │ Name          │ Namespace │ Chunks │ 📅 ││
│          │  │  📁 work     │  │───┼───────────────┼───────────┼────────┼────┤│
│          │  │     (8)      │  │ □ │ README.md     │ personal  │ 3      │ 📅 ││
│          │  │  📁 projects │  │ □ │ notes.md      │ personal  │ 5      │ 📅 ││
│          │  │     (3)      │  │ □ │ meeting.md    │ work      │ 2      │ 📅 ││
│          │  │              │  │ ☑ │ todo.md       │ work      │ 1      │ 📅 ││
│          │  │  ─────────── │  │ □ │ api-docs.md   │ projects  │ 8      │ 📅 ││
│          │  │  ➕ New      │  └───────────────────────────────────────────┘│
│          │  │     Folder   │                                                  │
│          │  │              │  [◀ Prev] Page 1 of 3 [Next ▶]    23 items      │
│          │  └──────────────┘                                                  │
│          │                                                                  │
└──────────┴──────────────────────────────────────────────────────────────────┘
```

## Wireframe - Upload Modal

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Documents                                     [⬆️ Upload] [≡]              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                           ⬆️ Upload Files                              │  │
│  │                                                                       │  │
│  │                    ┌─────────────────────────┐                        │  │
│  │                    │                         │                        │  │
│  │                    │    📄 ⬆️ 📄 ⬆️ 📄      │                        │  │
│  │                    │                         │                        │  │
│  │                    │   Drop files here       │                        │  │
│  │                    │   or click to browse    │                        │  │
│  │                    │                         │                        │  │
│  │                    │   Supports: .md, .txt   │                        │  │
│  │                    └─────────────────────────┘                        │  │
│  │                                                                       │  │
│  │   Namespace: [📁 work ▼]  [➕ New Namespace]                          │  │
│  │                                                                       │  │
│  │   ⏳ Uploading...                                                     │  │
│  │   ┌────────────────────────────────────────────────────────────────┐  │  │
│  │   │ 📄 notes.md                    ████████████░░░░  80%          │  │  │
│  │   │ 📄 readme.md                   ██████░░░░░░░░░░  40%          │  │  │
│  │   │ 📄 api.md                      ░░░░░░░░░░░░░░░░  pending      │  │  │
│  │   └────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │   [Cancel]                              [Upload 3 files]              │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Wireframe - Grid View

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Documents                                     [⬆️ Upload] [☰] [□]         │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┬──────────────────────────────────────────────────────────┤
│  │ Namespaces   │  work (8 files)                                           │
│  │   ...        │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐         │
│  │              │  │ 📄          │ │ 📄          │ │ 📄          │         │
│  │              │  │             │ │             │ │             │         │
│  │              │  │ README.md   │ │ notes.md    │ │ todo.md     │         │
│  │              │  │             │ │             │ │             │         │
│  │              │  │ 3 chunks    │ │ 5 chunks    │ │ 1 chunk     │         │
│  │              │  │ 📅 2h ago   │ │ 📅 1d ago   │ │ 📅 3d ago   │         │
│  │              │  └─────────────┘ └─────────────┘ └─────────────┘         │
│  │              │  ┌─────────────┐ ┌─────────────┐                         │
│  │              │  │ 📄          │ │ 📄          │                         │
│  │              │  │             │ │             │                         │
│  │              │  │ api.md      │ │ ...         │                         │
│  │              │  │             │ │             │                         │
│  │              │  └─────────────┘ └─────────────┘                         │
│  └──────────────┴──────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Layout

- **Left sidebar (250px):** Namespace tree
- **Main area:** Document list/grid
- **Modal:** Upload interface

---

## Sections

### 1. Namespace Sidebar

**Tree Structure:**
```
📁 All (23)
  📁 personal (12)
    📄 file1.md
    📄 file2.md
  📁 work (8)
  📁 projects (3)
```

**Interactions:**
- Click namespace → Filter documents
- Right-click → Context menu (rename, delete, refresh)
- Drag files between namespaces (if supported)
- "New Folder" button → Create namespace

**Context Menu:**
- Rename
- Delete (with confirmation)
- Refresh index
- Export documents

### 2. Document List

**Table Columns:**
| Column | Sortable | Description |
|--------|----------|-------------|
| Checkbox | No | Bulk select |
| Name | Yes | Filename |
| Namespace | Yes | Parent namespace |
| Chunks | Yes | Number of chunks |
| Date | Yes | Upload date |
| Actions | No | View, Delete |

**Row Actions:**
- 👁️ View - Open preview modal
- 🗑️ Delete - Remove from index
- ⬇️ Download - Get original file

**Bulk Actions (when items selected):**
- Delete selected
- Move to namespace
- Re-index selected

### 3. Upload Modal

**States:**

**State 1: Empty DropZone**
- Large dashed border box
- "Drop files here or click to browse"
- Supported formats listed

**State 2: Files Selected**
- List of selected files
- Remove button per file
- Namespace dropdown
- "New Namespace" inline input

**State 3: Uploading**
- Progress bars per file
- Cancel button (per file and global)
- Estimated time remaining

**State 4: Complete**
- Success checkmark
- Summary: "3 files uploaded, 12 chunks created"
- "Upload more" or "Close" buttons

### 4. Document Preview Modal

```
┌─────────────────────────────────────────────────────────────────────┐
│  📄 notes.md                                    [✕]                 │
├─────────────────────────────────────────────────────────────────────┤
│  Namespace: personal                                                │
│  Size: 2.4 KB  |  Chunks: 5  |  Indexed: 2 hours ago               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  # Project Notes                                                    │
│                                                                     │
│  ## Meeting 2024-01-15                                              │
│                                                                     │
│  - Discussed API design                                             │
│  - Action items assigned                                            │
│                                                                     │
│  ## Technical Details                                               │
│  ...                                                                │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  [⬇️ Download]  [🔄 Re-index]  [🗑️ Delete]                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## View Modes

| Mode | Icon | Use Case |
|------|------|----------|
| List | ☰ | Detailed view, sorting, bulk actions |
| Grid | □ | Visual browsing, quick overview |

---

## Components Needed

| Component | File |
|-----------|------|
| NamespaceTree | `components/documents/NamespaceTree.tsx` |
| DocumentTable | `components/documents/DocumentTable.tsx` |
| DocumentGrid | `components/documents/DocumentGrid.tsx` |
| UploadModal | `components/documents/UploadModal.tsx` |
| DocumentPreview | `components/documents/DocumentPreview.tsx` |
| NamespaceMenu | `components/documents/NamespaceMenu.tsx` |
| BulkActionBar | `components/documents/BulkActionBar.tsx` |

---

## API Endpoints

```typescript
// Fetch documents
GET /api/status                    // Get namespaces + counts

// Upload
POST /api/upload                   // Upload file
  Body: multipart/form-data
  
// Delete
DELETE /api/namespace/:id          // Remove from index (if supported)

// Jobs (for upload progress)
GET /api/jobs/:id                  // Check upload status
```

---

## State Management

```typescript
interface DocumentsState {
  namespaces: Namespace[];
  documents: Document[];
  selectedNamespace: string | null;
  selectedDocuments: string[];
  viewMode: 'list' | 'grid';
  uploadModalOpen: boolean;
  previewDocument: Document | null;
  
  // Actions
  fetchNamespaces: () => Promise<void>;
  uploadFiles: (files: File[], namespace: string) => Promise<void>;
  deleteDocument: (id: string) => Promise<void>;
  selectAll: () => void;
  clearSelection: () => void;
}
```

---

## Empty States

**No Namespaces:**
```
┌─────────────────────────────────────┐
│           📁                        │
│     No namespaces yet               │
│                                     │
│  Create your first namespace        │
│  to organize your documents         │
│                                     │
│     [Create Namespace]              │
└─────────────────────────────────────┘
```

**Namespace Empty:**
```
┌─────────────────────────────────────┐
│  work (0 files)                     │
│                                     │
│     📄                              │
│  No documents in this namespace     │
│                                     │
│  [Upload Files to work]             │
└─────────────────────────────────────┘
```

---

## Responsive

| Breakpoint | Layout |
|------------|--------|
| Desktop | Sidebar visible, table view |
| Tablet | Collapsible sidebar |
| Mobile | Full-screen list, no sidebar (use dropdown) |
