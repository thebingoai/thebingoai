# IMPLEMENTATION_08: Settings Page

## Overview
Complete implementation plan for a comprehensive Settings page with system configuration, provider management, embedding settings, appearance customization, and data management.

## Backend APIs

### Health Check
```
GET /health

Response:
{
  status: "healthy" | "degraded" | "unhealthy"
}
```

### Detailed Health Check
```
GET /health/detailed

Response:
{
  status: "healthy" | "degraded" | "unhealthy",
  checks: {
    api: { status: boolean, error?: string },
    redis: { status: boolean, error?: string },
    pinecone: { status: boolean, error?: string },
    pinecone_vectors?: { status: boolean, error?: string }
  }
}
```

### Get Providers
```
GET /api/providers

Response:
{
  providers: [
    {
      name: "openai" | "anthropic" | "ollama",
      available: boolean,
      models: [
        {
          id: string,
          name: string,
          description?: string
        }
      ],
      error?: string
    }
  ],
  default: {
    provider: string,
    model: string
  }
}
```

### Test Connection
```
POST /api/settings/test-connection

Body: { backend_url: string }

Response: { success: boolean, message?: string }
```

### Save Settings
```
POST /api/settings

Body: {
  backend_url?: string,
  default_namespace?: string,
  default_provider?: string,
  default_model?: string,
  chunk_size?: number,
  chunk_overlap?: number,
  embedding_model?: string,
  theme?: "light" | "dark" | "system",
  density?: "comfortable" | "compact",
  font_size?: "small" | "medium" | "large",
  animations_enabled?: boolean
}

Response: { success: boolean }
```

### Clear Cache
```
POST /api/settings/cache/clear

Response: { success: boolean, freed_bytes: number }
```

### Export Data
```
GET /api/settings/export?type=index|conversations|settings

Response: JSON file download
```

### Import Data
```
POST /api/settings/import

Body: FormData with file

Response: { success: boolean, imported_items: number }
```

---

## Components

### 1. SettingsPage.tsx
**Path:** `src/pages/SettingsPage.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import { useSettingsStore } from '@/stores/useSettingsStore';
import { GeneralSettings } from '@/components/settings/GeneralSettings';
import { ProviderSettings } from '@/components/settings/ProviderSettings';
import { EmbeddingSettings } from '@/components/settings/EmbeddingSettings';
import { AppearanceSettings } from '@/components/settings/AppearanceSettings';
import { DataSettings } from '@/components/settings/DataSettings';
import { AboutSection } from '@/components/settings/AboutSection';
import { Dialog } from '@/components/shared/Dialog';
import { AlertCircle } from 'lucide-react';

type SettingsTab =
  | 'general'
  | 'providers'
  | 'embedding'
  | 'appearance'
  | 'data'
  | 'about';

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('general');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [showUnsavedDialog, setShowUnsavedDialog] = useState(false);
  const [nextTab, setNextTab] = useState<SettingsTab | null>(null);
  const settingsStore = useSettingsStore();

  const tabs: { id: SettingsTab; label: string; icon: string }[] = [
    { id: 'general', label: 'General', icon: '⚙️' },
    { id: 'providers', label: 'LLM Providers', icon: '🤖' },
    { id: 'embedding', label: 'Embedding', icon: '🧬' },
    { id: 'appearance', label: 'Appearance', icon: '🎨' },
    { id: 'data', label: 'Data', icon: '💾' },
    { id: 'about', label: 'About', icon: 'ℹ️' },
  ];

  const handleTabChange = (tab: SettingsTab) => {
    if (hasUnsavedChanges) {
      setNextTab(tab);
      setShowUnsavedDialog(true);
    } else {
      setActiveTab(tab);
    }
  };

  const handleDiscardChanges = () => {
    settingsStore.discardChanges();
    setHasUnsavedChanges(false);
    if (nextTab) {
      setActiveTab(nextTab);
      setNextTab(null);
    }
    setShowUnsavedDialog(false);
  };

  const handleSaveAndContinue = async () => {
    await settingsStore.saveSettings();
    setHasUnsavedChanges(false);
    if (nextTab) {
      setActiveTab(nextTab);
      setNextTab(null);
    }
    setShowUnsavedDialog(false);
  };

  return (
    <div className="flex-1 overflow-auto bg-white dark:bg-slate-950">
      <div className="flex h-full">
        {/* Sidebar */}
        <div className="w-48 border-r border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 overflow-y-auto">
          <div className="sticky top-0 z-10 px-4 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900">
            <h1 className="text-lg font-bold text-slate-900 dark:text-white">
              Settings
            </h1>
          </div>

          <nav className="p-3 space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                    : 'text-slate-700 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-300 hover:bg-white/50 dark:hover:bg-slate-800/50'
                }`}
              >
                <span className="mr-2">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-6 py-8">
            {hasUnsavedChanges && (
              <div className="mb-6 p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-amber-900 dark:text-amber-100">
                    Unsaved changes
                  </p>
                  <p className="text-sm text-amber-800 dark:text-amber-200 mt-0.5">
                    You have unsaved changes. Save them before navigating away.
                  </p>
                </div>
              </div>
            )}

            {activeTab === 'general' && (
              <GeneralSettings onChanges={() => setHasUnsavedChanges(true)} />
            )}
            {activeTab === 'providers' && (
              <ProviderSettings onChanges={() => setHasUnsavedChanges(true)} />
            )}
            {activeTab === 'embedding' && (
              <EmbeddingSettings onChanges={() => setHasUnsavedChanges(true)} />
            )}
            {activeTab === 'appearance' && (
              <AppearanceSettings onChanges={() => setHasUnsavedChanges(true)} />
            )}
            {activeTab === 'data' && (
              <DataSettings onChanges={() => setHasUnsavedChanges(true)} />
            )}
            {activeTab === 'about' && (
              <AboutSection />
            )}
          </div>
        </div>
      </div>

      {/* Unsaved Changes Dialog */}
      <Dialog
        open={showUnsavedDialog}
        onOpenChange={setShowUnsavedDialog}
        title="Unsaved Changes"
      >
        <div className="space-y-4">
          <p className="text-slate-600 dark:text-slate-400">
            You have unsaved changes. Would you like to save them before leaving this section?
          </p>

          <div className="flex gap-2 justify-end">
            <button
              onClick={handleDiscardChanges}
              className="px-4 py-2 text-sm font-medium text-red-600 dark:text-red-400 border border-red-300 dark:border-red-700 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
            >
              Discard
            </button>
            <button
              onClick={handleSaveAndContinue}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 dark:bg-blue-700 rounded-lg hover:bg-blue-700 dark:hover:bg-blue-800 transition-colors"
            >
              Save Changes
            </button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
```

---

### 2. GeneralSettings.tsx
**Path:** `src/components/settings/GeneralSettings.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import { useSettingsStore } from '@/stores/useSettingsStore';
import { Check, AlertCircle, Loader2 } from 'lucide-react';

interface GeneralSettingsProps {
  onChanges: () => void;
}

export function GeneralSettings({ onChanges }: GeneralSettingsProps) {
  const settingsStore = useSettingsStore();
  const [backendUrl, setBackendUrl] = useState(settingsStore.backendUrl);
  const [defaultNamespace, setDefaultNamespace] = useState(
    settingsStore.defaultNamespace || ''
  );
  const [defaultProvider, setDefaultProvider] = useState(
    settingsStore.defaultProvider || 'openai'
  );
  const [defaultModel, setDefaultModel] = useState(
    settingsStore.defaultModel || 'gpt-4'
  );
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<
    'idle' | 'connected' | 'error'
  >('idle');
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const handleBackendUrlChange = (newUrl: string) => {
    setBackendUrl(newUrl);
    setConnectionStatus('idle');
    settingsStore.updateSetting('backendUrl', newUrl);
    onChanges();
  };

  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    try {
      const response = await fetch('/api/settings/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ backend_url: backendUrl }),
      });

      if (response.ok) {
        setConnectionStatus('connected');
        setConnectionError(null);
      } else {
        const data = await response.json();
        setConnectionStatus('error');
        setConnectionError(data.message || 'Connection failed');
      }
    } catch (error) {
      setConnectionStatus('error');
      setConnectionError(
        error instanceof Error ? error.message : 'Connection failed'
      );
    } finally {
      setIsTestingConnection(false);
    }
  };

  const handleSave = async () => {
    try {
      settingsStore.updateSetting('backendUrl', backendUrl);
      settingsStore.updateSetting('defaultNamespace', defaultNamespace);
      settingsStore.updateSetting('defaultProvider', defaultProvider);
      settingsStore.updateSetting('defaultModel', defaultModel);

      await settingsStore.saveSettings();
      // Show success toast
    } catch (error) {
      console.error('Failed to save settings:', error);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">
          General Settings
        </h2>

        {/* Backend URL */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Backend URL
            </label>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">
              The URL of your backend API server
            </p>
            <div className="flex gap-2">
              <input
                type="url"
                value={backendUrl}
                onChange={(e) => handleBackendUrlChange(e.target.value)}
                placeholder="https://api.example.com"
                className="flex-1 px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={handleTestConnection}
                disabled={isTestingConnection}
                className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                {isTestingConnection ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  'Test'
                )}
              </button>
            </div>

            {connectionStatus === 'connected' && (
              <div className="mt-2 flex items-center gap-2 text-green-600 dark:text-green-400 text-sm">
                <Check className="w-4 h-4" />
                Connection successful
              </div>
            )}
            {connectionStatus === 'error' && (
              <div className="mt-2 flex items-center gap-2 text-red-600 dark:text-red-400 text-sm">
                <AlertCircle className="w-4 h-4" />
                {connectionError || 'Connection failed'}
              </div>
            )}
          </div>

          {/* Default Namespace */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Default Namespace
            </label>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">
              Used for new documents and searches if not specified
            </p>
            <input
              type="text"
              value={defaultNamespace}
              onChange={(e) => {
                setDefaultNamespace(e.target.value);
                settingsStore.updateSetting('defaultNamespace', e.target.value);
                onChanges();
              }}
              placeholder="default"
              className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Default Provider */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Default LLM Provider
            </label>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">
              Provider to use for AI requests
            </p>
            <select
              value={defaultProvider}
              onChange={(e) => {
                setDefaultProvider(e.target.value);
                settingsStore.updateSetting('defaultProvider', e.target.value);
                onChanges();
              }}
              className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="ollama">Ollama</option>
            </select>
          </div>

          {/* Default Model */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Default Model
            </label>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">
              Model to use for AI requests
            </p>
            <input
              type="text"
              value={defaultModel}
              onChange={(e) => {
                setDefaultModel(e.target.value);
                settingsStore.updateSetting('defaultModel', e.target.value);
                onChanges();
              }}
              placeholder="gpt-4"
              className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          className="px-6 py-2 text-sm font-medium text-white bg-blue-600 dark:bg-blue-700 rounded-lg hover:bg-blue-700 dark:hover:bg-blue-800 transition-colors"
        >
          Save Changes
        </button>
      </div>
    </div>
  );
}
```

---

### 3. ProviderSettings.tsx
**Path:** `src/components/settings/ProviderSettings.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import { Dialog } from '@/components/shared/Dialog';
import { Eye, EyeOff, Loader2, Check, AlertCircle } from 'lucide-react';

interface Provider {
  name: 'openai' | 'anthropic' | 'ollama';
  available: boolean;
  models: Array<{ id: string; name: string; description?: string }>;
  error?: string;
}

interface ProviderSettingsProps {
  onChanges: () => void;
}

const PROVIDER_ICONS: Record<string, string> = {
  openai: '🔴',
  anthropic: '🧠',
  ollama: '🦙',
};

export function ProviderSettings({ onChanges }: ProviderSettingsProps) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedProvider, setSelectedProvider] = useState<'openai' | 'anthropic' | 'ollama' | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [selectedModel, setSelectedModel] = useState('');
  const [isTesting, setIsTesting] = useState(false);
  const [testStatus, setTestStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [testError, setTestError] = useState<string | null>(null);

  useEffect(() => {
    fetchProviders();
  }, []);

  const fetchProviders = async () => {
    try {
      const response = await fetch('/api/providers');
      const data = await response.json();
      setProviders(data.providers);
    } catch (error) {
      console.error('Failed to fetch providers:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleEditProvider = (name: 'openai' | 'anthropic' | 'ollama') => {
    setSelectedProvider(name);
    setApiKey('');
    setShowApiKey(false);
    setSelectedModel('');
    setTestStatus('idle');
    setShowEditModal(true);
  };

  const handleTestProvider = async () => {
    setIsTesting(true);
    try {
      const response = await fetch('/api/providers/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: selectedProvider,
          api_key: apiKey,
          model: selectedModel,
        }),
      });

      if (response.ok) {
        setTestStatus('success');
        setTestError(null);
      } else {
        const data = await response.json();
        setTestStatus('error');
        setTestError(data.message || 'Test failed');
      }
    } catch (error) {
      setTestStatus('error');
      setTestError(error instanceof Error ? error.message : 'Test failed');
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveProvider = async () => {
    try {
      await fetch('/api/providers/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: selectedProvider,
          api_key: apiKey,
          default_model: selectedModel,
        }),
      });

      await fetchProviders();
      setShowEditModal(false);
      onChanges();
    } catch (error) {
      console.error('Failed to save provider:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">
          LLM Providers
        </h2>

        <div className="space-y-4">
          {providers.map((provider) => (
            <div
              key={provider.name}
              className="p-4 border border-slate-200 dark:border-slate-800 rounded-lg"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{PROVIDER_ICONS[provider.name]}</span>
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900 dark:text-white capitalize">
                      {provider.name}
                    </h3>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span
                        className={`inline-block w-2 h-2 rounded-full ${
                          provider.available
                            ? 'bg-green-500'
                            : 'bg-red-500'
                        }`}
                      />
                      <p className="text-xs text-slate-600 dark:text-slate-400">
                        {provider.available ? 'Configured' : 'Not configured'}
                      </p>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => handleEditProvider(provider.name)}
                  className="px-3 py-1.5 text-xs font-medium text-blue-600 dark:text-blue-400 border border-blue-300 dark:border-blue-700 rounded hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
                >
                  Edit
                </button>
              </div>

              {provider.error && (
                <div className="p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded mb-3">
                  <p className="text-xs text-red-700 dark:text-red-300">
                    {provider.error}
                  </p>
                </div>
              )}

              {provider.models.length > 0 && (
                <div>
                  <p className="text-xs text-slate-600 dark:text-slate-400 font-medium mb-2">
                    Available Models
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {provider.models.map((model) => (
                      <span
                        key={model.id}
                        className="inline-block px-2.5 py-1 bg-slate-100 dark:bg-slate-800 text-xs text-slate-700 dark:text-slate-300 rounded"
                      >
                        {model.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Edit Provider Modal */}
      <Dialog
        open={showEditModal}
        onOpenChange={setShowEditModal}
        title={`Edit ${selectedProvider} Settings`}
      >
        <div className="space-y-4">
          {/* API Key Input */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              {selectedProvider === 'ollama' ? 'Server URL' : 'API Key'}
            </label>
            <div className="relative">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  setTestStatus('idle');
                }}
                placeholder={
                  selectedProvider === 'ollama'
                    ? 'http://localhost:11434'
                    : 'sk-...'
                }
                className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {selectedProvider !== 'ollama' && (
                <button
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                >
                  {showApiKey ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              )}
            </div>
          </div>

          {/* Model Selector */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Default Model
            </label>
            <select
              value={selectedModel}
              onChange={(e) => {
                setSelectedModel(e.target.value);
                setTestStatus('idle');
              }}
              className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a model</option>
              {providers
                .find((p) => p.name === selectedProvider)
                ?.models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                  </option>
                ))}
            </select>
          </div>

          {/* Test Status */}
          {testStatus === 'success' && (
            <div className="p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg flex items-center gap-2">
              <Check className="w-4 h-4 text-green-600 dark:text-green-400" />
              <p className="text-sm text-green-700 dark:text-green-300">
                Connection successful
              </p>
            </div>
          )}

          {testStatus === 'error' && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700 dark:text-red-300">
                {testError || 'Connection failed'}
              </p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-2 justify-end pt-2">
            <button
              onClick={() => setShowEditModal(false)}
              className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleTestProvider}
              disabled={isTesting || !apiKey || !selectedModel}
              className="px-4 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 border border-blue-300 dark:border-blue-700 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/20 disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              {isTesting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                'Test'
              )}
            </button>
            <button
              onClick={handleSaveProvider}
              disabled={!apiKey || !selectedModel}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 dark:bg-blue-700 rounded-lg hover:bg-blue-700 dark:hover:bg-blue-800 disabled:opacity-50 transition-colors"
            >
              Save
            </button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
```

---

### 4. EmbeddingSettings.tsx
**Path:** `src/components/settings/EmbeddingSettings.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import { useSettingsStore } from '@/stores/useSettingsStore';

interface EmbeddingSettingsProps {
  onChanges: () => void;
}

export function EmbeddingSettings({ onChanges }: EmbeddingSettingsProps) {
  const settingsStore = useSettingsStore();
  const [chunkSize, setChunkSize] = useState(settingsStore.chunkSize || 1024);
  const [chunkOverlap, setChunkOverlap] = useState(settingsStore.chunkOverlap || 20);
  const [embeddingModel, setEmbeddingModel] = useState(
    settingsStore.embeddingModel || 'text-embedding-3-small'
  );

  const DEFAULT_CHUNK_SIZE = 1024;
  const DEFAULT_OVERLAP = 20;

  const calculateChunks = () => {
    const wordsPerToken = 4 / 3;
    const inputTokens = 100000;
    const estimatedWords = inputTokens * wordsPerToken;

    const overlap = chunkSize * (chunkOverlap / 100);
    const effectiveSize = chunkSize - overlap;
    const chunks = Math.ceil(estimatedWords / effectiveSize);

    return chunks;
  };

  const handleSave = async () => {
    settingsStore.updateSetting('chunkSize', chunkSize);
    settingsStore.updateSetting('chunkOverlap', chunkOverlap);
    settingsStore.updateSetting('embeddingModel', embeddingModel);

    try {
      await settingsStore.saveSettings();
    } catch (error) {
      console.error('Failed to save settings:', error);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">
          Embedding Settings
        </h2>

        <div className="space-y-8">
          {/* Chunk Size */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                Chunk Size
              </label>
              <button
                onClick={() => setChunkSize(DEFAULT_CHUNK_SIZE)}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
              >
                Reset to default ({DEFAULT_CHUNK_SIZE})
              </button>
            </div>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-3">
              Number of tokens per chunk (100-2000)
            </p>
            <div className="flex gap-4 items-center">
              <input
                type="range"
                min="100"
                max="2000"
                step="100"
                value={chunkSize}
                onChange={(e) => {
                  setChunkSize(parseInt(e.target.value));
                  onChanges();
                }}
                className="flex-1"
              />
              <input
                type="number"
                min="100"
                max="2000"
                value={chunkSize}
                onChange={(e) => {
                  setChunkSize(Math.min(2000, Math.max(100, parseInt(e.target.value) || 0)));
                  onChanges();
                }}
                className="w-20 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Chunk Overlap */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                Chunk Overlap
              </label>
              <button
                onClick={() => setChunkOverlap(DEFAULT_OVERLAP)}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
              >
                Reset to default ({DEFAULT_OVERLAP}%)
              </button>
            </div>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-3">
              Percentage of overlap between chunks for context continuity (0-50%)
            </p>
            <div className="flex gap-4 items-center">
              <input
                type="range"
                min="0"
                max="50"
                step="5"
                value={chunkOverlap}
                onChange={(e) => {
                  setChunkOverlap(parseInt(e.target.value));
                  onChanges();
                }}
                className="flex-1"
              />
              <span className="w-12 text-right text-sm font-medium text-slate-700 dark:text-slate-300">
                {chunkOverlap}%
              </span>
            </div>
          </div>

          {/* Embedding Model */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Embedding Model
            </label>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-3">
              Model used for generating embeddings
            </p>
            <select
              value={embeddingModel}
              onChange={(e) => {
                setEmbeddingModel(e.target.value);
                onChanges();
              }}
              className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="text-embedding-3-small">
                OpenAI text-embedding-3-small
              </option>
              <option value="text-embedding-3-large">
                OpenAI text-embedding-3-large
              </option>
              <option value="text-embedding-ada-002">
                OpenAI text-embedding-ada-002
              </option>
              <option value="multilingual-e5-large">
                Multilingual E5 Large
              </option>
            </select>
          </div>

          {/* Preview Calculator */}
          <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
            <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-100 mb-2">
              Preview
            </h4>
            <p className="text-sm text-blue-800 dark:text-blue-200">
              A document with ~100,000 tokens would be split into approximately{' '}
              <strong>{calculateChunks()}</strong> chunks with current settings.
            </p>
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          className="px-6 py-2 text-sm font-medium text-white bg-blue-600 dark:bg-blue-700 rounded-lg hover:bg-blue-700 dark:hover:bg-blue-800 transition-colors"
        >
          Save Changes
        </button>
      </div>
    </div>
  );
}
```

---

### 5. AppearanceSettings.tsx
**Path:** `src/components/settings/AppearanceSettings.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import { useSettingsStore } from '@/stores/useSettingsStore';
import { Sun, Moon, Monitor } from 'lucide-react';

interface AppearanceSettingsProps {
  onChanges: () => void;
}

type Theme = 'light' | 'dark' | 'system';
type Density = 'comfortable' | 'compact';
type FontSize = 'small' | 'medium' | 'large';

export function AppearanceSettings({ onChanges }: AppearanceSettingsProps) {
  const settingsStore = useSettingsStore();
  const [theme, setTheme] = useState<Theme>(
    (settingsStore.theme as Theme) || 'system'
  );
  const [density, setDensity] = useState<Density>(
    (settingsStore.density as Density) || 'comfortable'
  );
  const [fontSize, setFontSize] = useState<FontSize>(
    (settingsStore.fontSize as FontSize) || 'medium'
  );
  const [animationsEnabled, setAnimationsEnabled] = useState(
    settingsStore.animationsEnabled !== false
  );

  const themes: { id: Theme; label: string; icon: React.ReactNode }[] = [
    { id: 'light', label: 'Light', icon: <Sun className="w-5 h-5" /> },
    { id: 'dark', label: 'Dark', icon: <Moon className="w-5 h-5" /> },
    { id: 'system', label: 'System', icon: <Monitor className="w-5 h-5" /> },
  ];

  const handleThemeChange = (newTheme: Theme) => {
    setTheme(newTheme);
    settingsStore.updateSetting('theme', newTheme);
    onChanges();

    // Apply theme
    if (newTheme === 'dark') {
      document.documentElement.classList.add('dark');
    } else if (newTheme === 'light') {
      document.documentElement.classList.remove('dark');
    } else {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (prefersDark) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }
  };

  const handleDensityChange = (newDensity: Density) => {
    setDensity(newDensity);
    settingsStore.updateSetting('density', newDensity);
    document.documentElement.setAttribute('data-density', newDensity);
    onChanges();
  };

  const handleFontSizeChange = (newSize: FontSize) => {
    setFontSize(newSize);
    settingsStore.updateSetting('fontSize', newSize);
    document.documentElement.setAttribute('data-font-size', newSize);
    onChanges();
  };

  const handleAnimationsChange = (enabled: boolean) => {
    setAnimationsEnabled(enabled);
    settingsStore.updateSetting('animationsEnabled', enabled);
    if (!enabled) {
      document.documentElement.style.setProperty('--animation-duration', '0s');
    } else {
      document.documentElement.style.removeProperty('--animation-duration');
    }
    onChanges();
  };

  const handleSave = async () => {
    try {
      await settingsStore.saveSettings();
    } catch (error) {
      console.error('Failed to save settings:', error);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">
          Appearance Settings
        </h2>

        <div className="space-y-8">
          {/* Theme Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
              Theme
            </label>
            <div className="grid grid-cols-3 gap-3">
              {themes.map((t) => (
                <button
                  key={t.id}
                  onClick={() => handleThemeChange(t.id)}
                  className={`flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-all ${
                    theme === t.id
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600'
                  }`}
                >
                  <div
                    className={`${
                      theme === t.id
                        ? 'text-blue-600 dark:text-blue-400'
                        : 'text-slate-600 dark:text-slate-400'
                    }`}
                  >
                    {t.icon}
                  </div>
                  <span
                    className={`text-xs font-medium ${
                      theme === t.id
                        ? 'text-blue-700 dark:text-blue-300'
                        : 'text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    {t.label}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Density */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
              Density
            </label>
            <div className="flex gap-3">
              {(['comfortable', 'compact'] as const).map((d) => (
                <button
                  key={d}
                  onClick={() => handleDensityChange(d)}
                  className={`flex-1 px-4 py-2 rounded-lg border-2 font-medium text-sm transition-all ${
                    density === d
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                      : 'border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600'
                  }`}
                >
                  {d.charAt(0).toUpperCase() + d.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Font Size */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
              Font Size
            </label>
            <div className="flex gap-3">
              {(['small', 'medium', 'large'] as const).map((size) => (
                <button
                  key={size}
                  onClick={() => handleFontSizeChange(size)}
                  className={`flex-1 px-4 py-2 rounded-lg border-2 font-medium transition-all ${
                    fontSize === size
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                      : 'border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600'
                  } ${
                    size === 'small'
                      ? 'text-xs'
                      : size === 'large'
                      ? 'text-base'
                      : 'text-sm'
                  }`}
                >
                  {size.charAt(0).toUpperCase() + size.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Animations */}
          <div>
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Animations
              </label>
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={animationsEnabled}
                  onChange={(e) => handleAnimationsChange(e.target.checked)}
                  className="rounded"
                />
                <span className="text-sm text-slate-600 dark:text-slate-400">
                  {animationsEnabled ? 'Enabled' : 'Disabled'}
                </span>
              </label>
            </div>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
              Enable or disable UI animations for reduced motion
            </p>
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          className="px-6 py-2 text-sm font-medium text-white bg-blue-600 dark:bg-blue-700 rounded-lg hover:bg-blue-700 dark:hover:bg-blue-800 transition-colors"
        >
          Save Changes
        </button>
      </div>
    </div>
  );
}
```

---

### 6. DataSettings.tsx
**Path:** `src/components/settings/DataSettings.tsx`

```typescript
import React, { useState } from 'react';
import { Dialog } from '@/components/shared/Dialog';
import { Download, Upload, Trash2, Loader2 } from 'lucide-react';

interface DataSettingsProps {
  onChanges: () => void;
}

export function DataSettings({ onChanges }: DataSettingsProps) {
  const [cacheSize, setCacheSize] = useState('24.5 MB');
  const [isClearing, setIsClearing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const handleClearCache = async () => {
    setIsClearing(true);
    try {
      const response = await fetch('/api/settings/cache/clear', {
        method: 'POST',
      });
      if (response.ok) {
        const data = await response.json();
        setCacheSize('0 KB');
        setShowClearConfirm(false);
      }
    } catch (error) {
      console.error('Failed to clear cache:', error);
    } finally {
      setIsClearing(false);
    }
  };

  const handleExport = async (type: 'index' | 'conversations' | 'settings') => {
    setIsExporting(true);
    try {
      const response = await fetch(`/api/settings/export?type=${type}`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${type}-export-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error('Failed to export data:', error);
    } finally {
      setIsExporting(false);
    }
  };

  const handleImport = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsImporting(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/settings/import', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        // Show success message
        console.log(`Imported ${data.imported_items} items`);
        onChanges();
      }
    } catch (error) {
      console.error('Failed to import data:', error);
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">
          Data Management
        </h2>

        <div className="space-y-6">
          {/* Cache Management */}
          <div>
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">
              Cache
            </h3>
            <div className="p-4 border border-slate-200 dark:border-slate-800 rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="text-sm text-slate-600 dark:text-slate-400">
                    Local cache size
                  </p>
                  <p className="text-lg font-semibold text-slate-900 dark:text-white mt-1">
                    {cacheSize}
                  </p>
                </div>
                <button
                  onClick={() => setShowClearConfirm(true)}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 dark:text-red-400 border border-red-300 dark:border-red-700 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                  Clear Cache
                </button>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Clearing cache will remove locally stored search results and
                embeddings, but won't affect your data on the server.
              </p>
            </div>
          </div>

          {/* Export Data */}
          <div>
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">
              Export
            </h3>
            <div className="space-y-2">
              {[
                { type: 'index' as const, label: 'Index Cache' },
                {
                  type: 'conversations' as const,
                  label: 'Conversations',
                },
                { type: 'settings' as const, label: 'Settings' },
              ].map((item) => (
                <button
                  key={item.type}
                  onClick={() => handleExport(item.type)}
                  disabled={isExporting}
                  className="w-full flex items-center gap-3 p-3 border border-slate-200 dark:border-slate-800 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-900/50 transition-colors disabled:opacity-50"
                >
                  <Download className="w-4 h-4 text-slate-600 dark:text-slate-400" />
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                    {item.label}
                  </span>
                  {isExporting && (
                    <Loader2 className="w-4 h-4 animate-spin ml-auto text-slate-400" />
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Import Data */}
          <div>
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">
              Import
            </h3>
            <label className="block">
              <input
                type="file"
                accept=".json"
                onChange={handleImport}
                disabled={isImporting}
                className="hidden"
              />
              <button
                onClick={(e) => {
                  const input = e.currentTarget.previousElementSibling as HTMLInputElement;
                  input?.click();
                }}
                disabled={isImporting}
                className="w-full flex items-center gap-3 p-3 border border-slate-200 dark:border-slate-800 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-900/50 transition-colors disabled:opacity-50"
              >
                <Upload className="w-4 h-4 text-slate-600 dark:text-slate-400" />
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  Import from backup
                </span>
                {isImporting && (
                  <Loader2 className="w-4 h-4 animate-spin ml-auto text-slate-400" />
                )}
              </button>
            </label>
          </div>
        </div>
      </div>

      {/* Clear Cache Confirmation */}
      <Dialog
        open={showClearConfirm}
        onOpenChange={setShowClearConfirm}
        title="Clear Cache"
      >
        <div className="space-y-4">
          <p className="text-slate-600 dark:text-slate-400">
            This will permanently delete all locally cached data. This action
            cannot be undone.
          </p>

          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setShowClearConfirm(false)}
              className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleClearCache}
              disabled={isClearing}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-600 dark:bg-red-700 rounded-lg hover:bg-red-700 dark:hover:bg-red-800 disabled:opacity-50 transition-colors"
            >
              {isClearing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
              Clear Cache
            </button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
```

---

### 7. AboutSection.tsx
**Path:** `src/components/settings/AboutSection.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import { ExternalLink } from 'lucide-react';

export function AboutSection() {
  const [versions, setVersions] = useState({
    app: '1.0.0',
    backend: 'loading...',
    buildDate: new Date().toLocaleDateString(),
  });

  useEffect(() => {
    const fetchVersions = async () => {
      try {
        const response = await fetch('/api/version');
        const data = await response.json();
        setVersions({
          app: data.app_version,
          backend: data.backend_version,
          buildDate: new Date(data.build_date).toLocaleDateString(),
        });
      } catch (error) {
        console.error('Failed to fetch version info:', error);
      }
    };

    fetchVersions();
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">
          About
        </h2>

        <div className="space-y-6">
          {/* Version Info */}
          <div className="p-4 border border-slate-200 dark:border-slate-800 rounded-lg">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-4">
              Version
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600 dark:text-slate-400">
                  App Version
                </span>
                <span className="text-sm font-medium text-slate-900 dark:text-white">
                  {versions.app}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600 dark:text-slate-400">
                  Backend Version
                </span>
                <span className="text-sm font-medium text-slate-900 dark:text-white">
                  {versions.backend}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600 dark:text-slate-400">
                  Build Date
                </span>
                <span className="text-sm font-medium text-slate-900 dark:text-white">
                  {versions.buildDate}
                </span>
              </div>
            </div>
          </div>

          {/* Tech Stack */}
          <div className="p-4 border border-slate-200 dark:border-slate-800 rounded-lg">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-4">
              Tech Stack
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold mb-1">
                  Frontend
                </p>
                <ul className="space-y-1 text-sm text-slate-700 dark:text-slate-300">
                  <li>React 18</li>
                  <li>TypeScript</li>
                  <li>Tailwind CSS</li>
                  <li>React Router</li>
                </ul>
              </div>
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold mb-1">
                  Backend
                </p>
                <ul className="space-y-1 text-sm text-slate-700 dark:text-slate-300">
                  <li>Python FastAPI</li>
                  <li>Redis</li>
                  <li>Pinecone</li>
                  <li>PostgreSQL</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Links */}
          <div className="space-y-2">
            <a
              href="/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 p-3 border border-slate-200 dark:border-slate-800 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-900/50 transition-colors"
            >
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Documentation
              </span>
              <ExternalLink className="w-4 h-4 text-slate-400 ml-auto" />
            </a>
            <a
              href="/issues"
              className="flex items-center gap-2 p-3 border border-slate-200 dark:border-slate-800 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-900/50 transition-colors"
            >
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Report a Bug
              </span>
              <ExternalLink className="w-4 h-4 text-slate-400 ml-auto" />
            </a>
          </div>

          {/* License */}
          <div className="p-4 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-lg">
            <p className="text-xs text-slate-600 dark:text-slate-400">
              <strong>License:</strong> MIT License
            </p>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-2">
              This software is provided as-is for personal and commercial use.
              See LICENSE file for details.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
```

---

## Store

### `src/stores/useSettingsStore.ts`

```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SettingsStore {
  // General
  backendUrl: string;
  defaultNamespace: string;
  defaultProvider: string;
  defaultModel: string;

  // Embedding
  chunkSize: number;
  chunkOverlap: number;
  embeddingModel: string;

  // Appearance
  theme: 'light' | 'dark' | 'system';
  density: 'comfortable' | 'compact';
  fontSize: 'small' | 'medium' | 'large';
  animationsEnabled: boolean;

  // Methods
  updateSetting: (key: string, value: any) => void;
  saveSettings: () => Promise<void>;
  discardChanges: () => void;
}

const defaultSettings = {
  backendUrl: 'http://localhost:8000',
  defaultNamespace: 'default',
  defaultProvider: 'openai',
  defaultModel: 'gpt-4',
  chunkSize: 1024,
  chunkOverlap: 20,
  embeddingModel: 'text-embedding-3-small',
  theme: 'system' as const,
  density: 'comfortable' as const,
  fontSize: 'medium' as const,
  animationsEnabled: true,
};

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set, get) => ({
      ...defaultSettings,

      updateSetting: (key, value) => {
        set({ [key]: value });
      },

      saveSettings: async () => {
        const state = get();
        const response = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            backend_url: state.backendUrl,
            default_namespace: state.defaultNamespace,
            default_provider: state.defaultProvider,
            default_model: state.defaultModel,
            chunk_size: state.chunkSize,
            chunk_overlap: state.chunkOverlap,
            embedding_model: state.embeddingModel,
            theme: state.theme,
            density: state.density,
            font_size: state.fontSize,
            animations_enabled: state.animationsEnabled,
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to save settings');
        }
      },

      discardChanges: () => {
        set(defaultSettings);
      },
    }),
    {
      name: 'settings-store',
    }
  )
);
```

---

## UI/UX Standards

### Form Sections
- Space between sections: `space-y-8`
- Space within sections: `space-y-4`
- Labels: `text-sm font-medium text-slate-700 dark:text-slate-300`
- Helper text: `text-sm text-slate-500 dark:text-slate-400 mt-1`
- Input fields: standard Tailwind form styling with focus ring

### Buttons
- Primary: `bg-blue-600 dark:bg-blue-700 hover:bg-blue-700 dark:hover:bg-blue-800`
- Secondary: `border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300`
- Destructive: `text-red-600 dark:text-red-400 border-red-300 dark:border-red-700`
- Disabled: `disabled:opacity-50 disabled:cursor-not-allowed`

### Status Indicators
- Success: `bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800`
- Error: `bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800`
- Warning: `bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800`
- Info: `bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800`

### Dark Mode
- All components support dark mode with `dark:` prefix
- Backgrounds: `dark:bg-slate-900`, `dark:bg-slate-950`
- Text: `dark:text-slate-300`, `dark:text-slate-400`
- Borders: `dark:border-slate-700`, `dark:border-slate-800`

### Responsive Design
- Sidebar hides on mobile (use hamburger menu)
- Single column layout for tablet/mobile
- Proper spacing and font sizes for all breakpoints

### Accessibility
- All form inputs have associated labels
- Color contrast meets WCAG AA standards
- Focus states visible with `:focus-ring-2 focus:ring-blue-500`
- Keyboard navigation fully supported
