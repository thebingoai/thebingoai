# Settings Page

**Route:** `/settings`  
**Purpose:** Configure application and backend settings  
**Priority:** P2

---

## Wireframe - Settings Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LLM-MD-CLI                              [🔍 Search...]    [🌙]    [⚙️]   │
├──────────┬──────────────────────────────────────────────────────────────────┤
│          │  ⚙️ Settings                                                     │
│  📊      │                                                                  │
│  📄 Docs │  ┌───────────────┬───────────────────────────────────────────────┤
│  🔍 Search│  │ Settings      │  Backend Connection                           │
│  💬 Chat │  │               │                                               │
│  ⚙️ Jobs │  │ ● General     │  Backend URL                                  │
│  ⚙️ Settings│  │   Backend     │  ┌─────────────────────────────────────────┐  │
│          │  │   LLM         │  │ http://localhost:8000            [Test] │  │
│          │  │   Embedding   │  └─────────────────────────────────────────┘  │
│          │  │   Appearance  │                                               │
│          │  │   Data        │  Status:  🟢 Connected                        │
│          │  │   About       │  Version: 0.1.0                               │
│          │  │               │                                               │
│          │  └───────────────┘  [Save Changes]                                │
│          │                                                                  │
│          │  ─────────────────────────────────────────────────────────────  │
│          │                                                                  │
│          │  Default Settings                                                │
│          │                                                                  │
│          │  Default Namespace:  [📁 All ▼]                                  │
│          │                                                                  │
│          │  Default Provider:   [🤖 openai ▼]                               │
│          │                                                                  │
│          │  Default Model:      [gpt-4o ▼]                                  │
│          │                                                                  │
└──────────┴──────────────────────────────────────────────────────────────────┘
```

---

## Settings Sections

### 1. Sidebar Navigation

**Categories:**
- ● **General** - Backend URL, defaults
- **Backend** - Connection settings
- **LLM** - Provider configuration
- **Embedding** - Chunk settings
- **Appearance** - Theme, density
- **Data** - Cache, export/import
- **About** - Version, info

---

## Page: General Settings

### Backend Connection

```
Backend URL
┌─────────────────────────────────────────────────────────────┐
│ http://localhost:8000                               [Test]  │
└─────────────────────────────────────────────────────────────┘

Status:  🟢 Connected
Version: 0.1.0
Uptime:  2 hours

[Save Changes]
```

**Test Connection Button:**
- Validates URL format
- Pings /health endpoint
- Shows success/error toast

### Default Settings

| Setting | Control | Options |
|---------|---------|---------|
| Default Namespace | Dropdown | All available namespaces |
| Default Provider | Dropdown | openai, anthropic, ollama |
| Default Model | Dropdown | Provider-specific models |

---

## Page: LLM Providers

### Provider Configuration

```
Configured Providers

┌─────────────────────────────────────────────────────────────┐
│ 🤖 OpenAI                                          [Edit ✎] │
│ Status: 🟢 Available                                        │
│ Models: gpt-4o, gpt-4-turbo, gpt-3.5-turbo                  │
│ Default: gpt-4o                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 🧠 Anthropic                                       [Edit ✎] │
│ Status: ⚪ Not Configured                                   │
│ Add API key to enable                                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 🦙 Ollama                                          [Edit ✎] │
│ Status: 🔴 Not Connected                                    │
│ URL: http://localhost:11434                                 │
└─────────────────────────────────────────────────────────────┘

[➕ Add Custom Provider]
```

### Add/Edit Provider Modal

```
┌─────────────────────────────────────────────────────────────┐
│ Configure Provider                                    [✕]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Provider:     [OpenAI ▼]                                    │
│                                                             │
│ API Key:      ┌─────────────────────────────────────────┐   │
│               │ sk-xxxxxxxxxxxxxxxxxxxxxxxxxx           │   │
│               └─────────────────────────────────────────┘   │
│               [👁️ Show]  [🔄 Test]                          │
│                                                             │
│ Default Model: [gpt-4o ▼]                                   │
│                                                             │
│ [Cancel]                                    [Save Provider] │
└─────────────────────────────────────────────────────────────┘
```

---

## Page: Embedding Settings

### Chunk Configuration

```
Document Processing

Chunk Size
┌─────────────────────────────────────────────────────────────┐
│ 512                                                [Default] │
└─────────────────────────────────────────────────────────────┘
Number of tokens per chunk (100-2000)

Chunk Overlap
┌─────────────────────────────────────────────────────────────┐
│ 20%                                                [Default] │
└─────────────────────────────────────────────────────────────┘
Percentage of overlap between chunks (0-50%)

Embedding Model
┌─────────────────────────────────────────────────────────────┐
│ text-embedding-3-large                             [Default] │
└─────────────────────────────────────────────────────────────┘
```

**Preview:**
```
Preview: A document with 1,500 tokens would create:
• ~3 chunks with current settings
• Total tokens including overlap: ~1,650
```

---

## Page: Appearance

### Theme

```
Theme

(●) 🌙 Dark
( ) ☀️ Light
( ) 🖥️ System (follows OS setting)

Preview:
┌─────────────────────────────────────────────┐
│  🌙 Dark Theme Preview                      │
│  This is how your interface will look       │
└─────────────────────────────────────────────┘
```

### Density

```
Layout Density

(●) Comfortable - More spacing, easier to read
( ) Compact - More content visible

Font Size
[ Small ] [ Medium ] [ Large ]
```

### Animations

```
Animations

[✓] Enable animations
[✓] Smooth scrolling
[ ] Reduced motion (accessibility)
```

---

## Page: Data Management

### Local Cache

```
Local Cache

Cache Size: 245 KB
Cached Items: 12 folders

[🗑️ Clear Cache]

This will remove local index cache but won't affect
indexed documents in Pinecone.
```

### Export Data

```
Export

[📥 Export Index Cache]
Save folder index metadata to JSON file

[📥 Export Conversations]
Download chat history

[📥 Export Settings]
Backup all configuration
```

### Import Data

```
Import

[📤 Import Index Cache]
Restore from backup file

⚠️ This will replace current cache data
```

---

## Page: About

```
LLM-MD-CLI Web UI

Version:     1.0.0
Backend:     0.1.0
Build Date:  2026-02-08

┌─────────────────────────────────────────────────────────────┐
│  Frontend: React 18 + TypeScript + Vite                    │
│  Backend:  FastAPI + Pinecone + LangGraph                  │
└─────────────────────────────────────────────────────────────┘

Links:
[📖 Documentation]  [🐛 Report Bug]  [💬 Discord]

License: MIT
© 2026 LLM-MD-CLI Contributors
```

---

## Components Needed

| Component | File |
|-----------|------|
| SettingsLayout | `components/settings/SettingsLayout.tsx` |
| SettingsSidebar | `components/settings/SettingsSidebar.tsx` |
| SettingsSection | `components/settings/SettingsSection.tsx` |
| ProviderCard | `components/settings/ProviderCard.tsx` |
| ProviderModal | `components/settings/ProviderModal.tsx` |
| ConnectionTest | `components/settings/ConnectionTest.tsx` |
| ThemePreview | `components/settings/ThemePreview.tsx` |
| DataExport | `components/settings/DataExport.tsx` |

---

## API Endpoints

```typescript
// Get settings
GET /api/settings

// Update settings
PUT /api/settings
  Body: Partial<Settings>

// Test backend connection
GET /health

// Get providers (with availability)
GET /api/providers

// Clear cache (local only)
DELETE /api/cache
```

---

## State Management

```typescript
interface SettingsState {
  backendUrl: string;
  connectionStatus: 'connected' | 'disconnected' | 'checking';
  
  // Defaults
  defaultNamespace: string;
  defaultProvider: string;
  defaultModel: string;
  
  // LLM
  providers: ProviderConfig[];
  
  // Embedding
  chunkSize: number;
  chunkOverlap: number;
  embeddingModel: string;
  
  // Appearance
  theme: 'dark' | 'light' | 'system';
  density: 'comfortable' | 'compact';
  fontSize: 'small' | 'medium' | 'large';
  animations: boolean;
  
  // Actions
  testConnection: () => Promise<void>;
  saveSettings: () => Promise<void>;
  addProvider: (config: ProviderConfig) => void;
  removeProvider: (id: string) => void;
  clearCache: () => Promise<void>;
  exportData: (type: string) => void;
  importData: (file: File) => Promise<void>;
}
```

---

## Form Validation

| Field | Validation | Error Message |
|-------|------------|---------------|
| Backend URL | Valid URL format | "Please enter a valid URL" |
| API Key | Min 20 chars | "API key is too short" |
| Chunk Size | 100-2000 | "Must be between 100 and 2000" |
| Chunk Overlap | 0-50 | "Must be between 0 and 50%" |

---

## Unsaved Changes Warning

If user tries to navigate away with unsaved changes:

```
┌─────────────────────────────────────────────────────────────┐
│ Unsaved Changes                                       [✕]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ You have unsaved changes. Are you sure you want to leave?   │
│                                                             │
│              [Cancel]              [Leave Without Saving]   │
└─────────────────────────────────────────────────────────────┘
```

---

## Success/Error Feedback

**Save Success:**
- Toast: "Settings saved successfully"
- Visual checkmark on save button

**Connection Test:**
- Success: Green checkmark, version info
- Error: Red X, error message

**Clear Cache:**
- Confirm dialog before action
- Success toast after completion
