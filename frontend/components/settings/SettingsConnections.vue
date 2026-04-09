<template>
  <div class="p-4 md:p-6">
    <div class="mb-6">
      <h2 class="text-2xl font-medium text-gray-900">Connections</h2>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex flex-wrap gap-4">
      <UiSkeleton class="h-56 w-56 max-md:w-full rounded-lg" />
      <UiSkeleton class="h-56 w-56 max-md:w-full rounded-lg" />
      <UiSkeleton class="h-56 w-56 max-md:w-full rounded-lg" />
    </div>

    <!-- Empty State -->
    <UiEmptyState
      v-else-if="connections.length === 0"
      title="No connections yet"
      description="Connect to your databases to start querying with AI"
      :icon="Database"
    >
      <template #action>
        <UiButton @click="openCreateDialog">
          Add Your First Connection
        </UiButton>
      </template>
    </UiEmptyState>

    <!-- Connections Grid -->
    <div v-else class="flex flex-wrap gap-4">
      <!-- Ungrouped connections (non-dataset or unique fingerprint datasets) -->
      <UiCard
        v-for="connection in ungroupedConnections"
        :key="connection.id"
        class="px-5 py-8 h-56 w-56 max-md:w-full cursor-pointer hover:shadow-lg transition-shadow"
        @click="openEditDialog(connection)"
      >
        <div class="flex flex-col h-full">
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-start gap-3 min-w-0">
              <div
                class="h-8 w-8 shrink-0"
                v-if="connectorIcons[connection.db_type]"
                v-html="connectorIcons[connection.db_type]"
              />
              <component v-else :is="Database" class="h-8 w-8 text-gray-400 shrink-0" />
              <p class="text-sm font-medium text-gray-900 truncate">{{ connection.name }}</p>
            </div>
            <span v-if="connection.is_active" class="flex items-center justify-center h-6 w-6 rounded-full bg-green-500 shrink-0">
              <Check class="h-3.5 w-3.5 text-white" />
            </span>
            <span v-else class="flex items-center justify-center h-6 w-6 rounded-full bg-red-500 shrink-0">
              <X class="h-3.5 w-3.5 text-white" />
            </span>
          </div>
          <div class="flex flex-wrap gap-1.5 mt-3">
            <UiBadge v-if="connection.db_type === 'dataset'" variant="secondary" size="sm">
              Dataset
            </UiBadge>
            <UiBadge v-if="connection.ssl_enabled" variant="success" size="sm">
              SSL
            </UiBadge>
          </div>
          <!-- Profiling status indicator -->
          <div v-if="connection.profiling_status" class="flex items-center gap-1.5 mt-2">
            <template v-if="connection.profiling_status === 'pending'">
              <span class="h-2 w-2 rounded-full bg-gray-400 shrink-0" />
              <span class="text-xs text-gray-500">Queued</span>
            </template>
            <template v-else-if="connection.profiling_status === 'in_progress'">
              <span class="h-2 w-2 rounded-full bg-yellow-400 animate-pulse shrink-0" />
              <span class="text-xs text-yellow-600">{{ connection.profiling_progress ? `Profiling ${connection.profiling_progress} tables...` : 'Profiling...' }}</span>
            </template>
            <template v-else-if="connection.profiling_status === 'ready'">
              <span class="h-2 w-2 rounded-full bg-green-500 shrink-0" />
              <span class="text-xs text-green-600">Ready</span>
            </template>
            <template v-else-if="connection.profiling_status === 'failed'">
              <span class="h-2 w-2 rounded-full bg-red-500 shrink-0" />
              <span class="text-xs text-red-500">Failed</span>
              <button
                @click.stop="handleReprofile(connection)"
                class="text-xs text-blue-600 hover:text-blue-700 underline ml-1"
              >
                Retry
              </button>
            </template>
          </div>
          <div class="mt-auto flex flex-col gap-0.5">
            <p v-if="connection.db_type === 'dataset' && connection.source_filename" class="text-xs text-gray-400 truncate">{{ connection.source_filename }}</p>
            <p v-else-if="connection.table_count != null" class="text-xs text-gray-400">{{ connection.table_count }} tables</p>
            <p v-if="connection.schema_generated_at" class="text-xs text-gray-400">{{ formatRelativeDate(connection.schema_generated_at) }}</p>
          </div>
        </div>
      </UiCard>

      <!-- Grouped dataset connections (shared schema_fingerprint) -->
      <UiCard
        v-for="group in datasetGroups"
        :key="group.fingerprint"
        class="px-5 py-5 w-56 max-md:w-full hover:shadow-lg transition-shadow"
        :class="{ 'h-56': !expandedGroups[group.fingerprint] }"
      >
        <div class="flex flex-col h-full">
          <button
            class="flex items-start justify-between gap-3 w-full text-left cursor-pointer"
            @click="toggleGroup(group.fingerprint)"
          >
            <div class="flex items-start gap-3 min-w-0">
              <div class="h-8 w-8 shrink-0" v-html="connectorIcons['dataset']" />
              <div class="min-w-0">
                <p class="text-sm font-medium text-gray-900 truncate">{{ group.name }}</p>
                <p class="text-xs text-gray-500">{{ group.connections.length }} datasets</p>
              </div>
            </div>
            <component :is="expandedGroups[group.fingerprint] ? ChevronDown : ChevronRight" class="h-4 w-4 text-gray-400 shrink-0 mt-1" />
          </button>
          <div class="flex flex-wrap gap-1.5 mt-3">
            <UiBadge variant="secondary" size="sm">Dataset Group</UiBadge>
          </div>
          <!-- Expanded: list individual datasets -->
          <div v-if="expandedGroups[group.fingerprint]" class="mt-3 space-y-2 border-t border-gray-100 pt-3">
            <div
              v-for="conn in group.connections"
              :key="conn.id"
              class="flex items-center justify-between gap-2 px-2 py-1.5 rounded hover:bg-gray-50 cursor-pointer"
              @click="openEditDialog(conn)"
            >
              <div class="min-w-0 flex-1">
                <p class="text-xs font-medium text-gray-700 truncate">{{ conn.name }}</p>
                <p v-if="conn.source_filename" class="text-xs text-gray-400 truncate">{{ conn.source_filename }}</p>
              </div>
              <button
                @click.stop="openDeleteDialog(conn)"
                class="text-gray-400 hover:text-red-500 shrink-0"
              >
                <Trash2 class="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          <div v-else class="mt-auto flex flex-col gap-0.5">
            <p class="text-xs text-gray-400">{{ group.connections.map(c => c.source_filename || c.name).join(', ') }}</p>
          </div>
        </div>
      </UiCard>

      <!-- Add Connection card -->
      <button
        @click="openCreateDialog"
        class="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-gray-300 rounded-lg h-56 w-56 max-md:w-full hover:border-gray-400 hover:bg-gray-50 transition-colors cursor-pointer"
      >
        <component :is="Plus" class="h-6 w-6 text-gray-400" />
        <span class="text-sm text-gray-500">Add Connection</span>
      </button>
    </div>

    <!-- Type Picker Bottom Sheet -->
    <UiBottomSheet
      :open="showTypePicker"
      @update:open="handleTypePickerClose"
      :title="typePickerTitle"
      fullHeight
    >
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 ml-auto">
        <button
          v-for="type in connectorTypes"
          :key="type.id"
          @click="selectConnectorType(type.id)"
          class="flex flex-col items-center justify-center gap-2 rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow cursor-pointer"
        >
          <div v-if="connectorIcons[type.id]" class="h-10 w-10" v-html="connectorIcons[type.id]" />
          <component v-else :is="Database" class="h-10 w-10 text-gray-400" />
          <div class="text-center">
            <h3 class="text-xs font-normal text-gray-900">{{ type.display_name }}</h3>
            <p class="text-xs text-gray-600">{{ type.description }}</p>
          </div>
        </button>
      </div>
    </UiBottomSheet>

    <!-- Connection Form Bottom Sheet -->
    <UiBottomSheet
      :open="showFormSheet"
      @update:open="handleFormSheetClose"
      :closable="false"
      panelClass="h-[calc(80vh-6rem)]"
    >
      <template #header>
        <div class="flex flex-col md:flex-row md:items-center md:justify-between w-full gap-2">
          <div class="flex items-center gap-3">
            <button
              v-if="!editingConnection"
              @click="goBackToTypePicker"
              class="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100"
            >
              <ArrowLeft class="h-5 w-5" />
            </button>
            <span class="text-lg font-normal text-gray-900">{{ getFormTitle() }}</span>
            <div v-if="testSuccess" class="flex items-center justify-center w-6 h-6 rounded-full bg-green-500">
              <Check class="h-3.5 w-3.5 text-white" />
            </div>
          </div>
          <div class="flex items-center gap-2">
            <UiButton
              variant="outline"
              size="sm"
              @click="showFormSheet = false"
            >
              Cancel
            </UiButton>
            <UiButton
              v-if="editingConnection"
              variant="outline"
              size="sm"
              :loading="refreshingId === editingConnection.id"
              @click.stop="refreshSchema(editingConnection)"
            >
              <RefreshCw class="h-3.5 w-3.5" />
              Refresh Schema
            </UiButton>
            <UiButton
              v-if="editingConnection"
              variant="outline"
              size="sm"
              :loading="reprofilingId === editingConnection.id"
              :disabled="editingConnection.profiling_status === 'in_progress'"
              @click.stop="handleReprofile(editingConnection)"
            >
              <RefreshCw class="h-3.5 w-3.5" />
              Reprofile
            </UiButton>
            <!-- File-upload connections: no Test or Save buttons (upload form handles submission) -->
            <template v-if="!isFileUploadConnection">
              <UiButton
                v-if="!testSuccess"
                variant="outline"
                size="sm"
                :loading="testing"
                @click="handleTestConnection"
              >
                Test Connection
              </UiButton>
              <UiButton
                size="sm"
                :loading="saving"
                @click="handleFormSubmit"
              >
                {{ editingConnection ? 'Save Changes' : 'Create Connection' }}
              </UiButton>
            </template>
            <button
              @click="handleFormSheetClose(false)"
              class="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            >
              <component :is="X" class="h-5 w-5" />
            </button>
          </div>
        </div>
      </template>

      <div class="flex flex-col md:flex-row">
        <!-- 40% form -->
        <div class="w-full md:w-2/5 md:pr-6 pb-4 md:pb-0">

          <!-- SQLite upload form (creating new sqlite connection) -->
          <template v-if="isSqliteConnection && !editingConnection">
            <form @submit.prevent="handleSqliteUpload" class="space-y-4">
              <UiInput
                v-model="sqliteForm.name"
                label="Database Name"
                placeholder="My SQLite Database"
                :error="sqliteFormErrors.name"
              />
              <div>
                <label class="text-sm font-normal text-gray-900 mb-1.5 block">File</label>
                <div
                  class="relative border-2 border-dashed rounded-lg p-6 text-center transition-colors"
                  :class="sqliteDragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'"
                  @dragover.prevent="sqliteDragOver = true"
                  @dragleave.prevent="sqliteDragOver = false"
                  @drop.prevent="handleSqliteDrop"
                >
                  <input
                    type="file"
                    accept=".sqlite,.db"
                    ref="sqliteFileInputRef"
                    @change="handleSqliteFileChange"
                    class="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  />
                  <div v-if="!sqliteFile">
                    <Database class="h-8 w-8 text-gray-400 mx-auto mb-2" />
                    <p class="text-sm text-gray-600">Drop a SQLite database file here</p>
                    <p class="text-xs text-gray-400 mt-1">or click to browse</p>
                    <p class="text-xs text-gray-400 mt-1">.sqlite or .db — max 50 MB</p>
                  </div>
                  <div v-else class="flex items-center gap-3 justify-center">
                    <Database class="h-5 w-5 text-blue-500 shrink-0" />
                    <div class="text-left min-w-0">
                      <p class="text-sm font-medium text-gray-900 truncate">{{ sqliteFile.name }}</p>
                      <p class="text-xs text-gray-500">{{ formatFileSize(sqliteFile.size) }}</p>
                    </div>
                    <button type="button" @click.stop="clearSqliteFile" class="ml-auto shrink-0 text-gray-400 hover:text-gray-600">
                      <component :is="X" class="h-4 w-4" />
                    </button>
                  </div>
                </div>
                <p v-if="sqliteFormErrors.file" class="text-xs text-red-500 mt-1">{{ sqliteFormErrors.file }}</p>
              </div>

              <!-- Table preview after upload -->
              <div v-if="sqliteUploadResult">
                <label class="text-sm font-normal text-gray-900 mb-1.5 block">Tables ({{ sqliteUploadResult.table_count }})</label>
                <div class="border border-gray-200 rounded-lg overflow-hidden">
                  <table class="w-full text-xs">
                    <thead class="bg-gray-50">
                      <tr>
                        <th class="px-3 py-2 text-left font-medium text-gray-600">Table</th>
                        <th class="px-3 py-2 text-right font-medium text-gray-600">Rows</th>
                        <th class="px-3 py-2 text-right font-medium text-gray-600">Columns</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="t in sqliteUploadResult.tables" :key="t.name" class="border-t border-gray-100">
                        <td class="px-3 py-1.5 text-gray-700 font-mono">{{ t.name }}</td>
                        <td class="px-3 py-1.5 text-gray-500 text-right">{{ t.row_count.toLocaleString() }}</td>
                        <td class="px-3 py-1.5 text-gray-500 text-right">{{ t.column_count }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <UiButton type="submit" class="w-full" :loading="uploadingSqlite" :disabled="!sqliteFile">
                Upload SQLite Database
              </UiButton>
            </form>
          </template>

          <!-- SQLite view (editing existing sqlite connection) -->
          <template v-else-if="isSqliteConnection && editingConnection">
            <div class="space-y-4">
              <div>
                <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">Database Name</label>
                <p class="text-sm text-gray-900 mt-0.5">{{ editingConnection.name }}</p>
              </div>
              <div v-if="editingConnection.source_filename">
                <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">Source File</label>
                <p class="text-sm text-gray-900 mt-0.5">{{ editingConnection.source_filename }}</p>
              </div>
            </div>
          </template>

          <!-- Dataset upload form (creating new dataset connection) -->
          <template v-else-if="isDatasetConnection && !editingConnection">
            <form @submit.prevent="handleDatasetUpload" class="space-y-4">
              <UiInput
                v-model="datasetForm.name"
                label="Dataset Name"
                placeholder="My Dataset"
                :error="datasetFormErrors.name"
              />
              <div>
                <label class="text-sm font-normal text-gray-900 mb-1.5 block">File</label>
                <div
                  class="relative border-2 border-dashed rounded-lg p-6 text-center transition-colors"
                  :class="datasetDragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'"
                  @dragover.prevent="datasetDragOver = true"
                  @dragleave.prevent="datasetDragOver = false"
                  @drop.prevent="handleDatasetDrop"
                >
                  <input
                    type="file"
                    accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    ref="datasetFileInputRef"
                    @change="handleDatasetFileChange"
                    class="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  />
                  <div v-if="!datasetFile">
                    <Sheet class="h-8 w-8 text-gray-400 mx-auto mb-2" />
                    <p class="text-sm text-gray-600">Drop a CSV or Excel file here</p>
                    <p class="text-xs text-gray-400 mt-1">or click to browse</p>
                    <p class="text-xs text-gray-400 mt-1">CSV or .xlsx — max 50 MB, 500K rows</p>
                  </div>
                  <div v-else class="flex items-center gap-3 justify-center">
                    <Sheet class="h-5 w-5 text-blue-500 shrink-0" />
                    <div class="text-left min-w-0">
                      <p class="text-sm font-medium text-gray-900 truncate">{{ datasetFile.name }}</p>
                      <p class="text-xs text-gray-500">{{ formatFileSize(datasetFile.size) }}</p>
                    </div>
                    <button type="button" @click.stop="clearDatasetFile" class="ml-auto shrink-0 text-gray-400 hover:text-gray-600">
                      <component :is="X" class="h-4 w-4" />
                    </button>
                  </div>
                </div>
                <p v-if="datasetFormErrors.file" class="text-xs text-red-500 mt-1">{{ datasetFormErrors.file }}</p>
              </div>

              <!-- Column preview for CSV -->
              <div v-if="datasetPreviewColumns.length > 0">
                <label class="text-sm font-normal text-gray-900 mb-1.5 block">Column Preview</label>
                <div class="border border-gray-200 rounded-lg overflow-hidden">
                  <table class="w-full text-xs">
                    <thead class="bg-gray-50">
                      <tr>
                        <th class="px-3 py-2 text-left font-medium text-gray-600">Column</th>
                        <th class="px-3 py-2 text-left font-medium text-gray-600">Detected Type</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="col in datasetPreviewColumns" :key="col.name" class="border-t border-gray-100">
                        <td class="px-3 py-1.5 text-gray-700 font-mono">{{ col.name }}</td>
                        <td class="px-3 py-1.5 text-gray-500 bg-gray-50 font-mono">{{ col.type }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Excel notice -->
              <div v-else-if="datasetFile && datasetFile.name.endsWith('.xlsx')" class="flex items-center gap-2 text-sm text-gray-500 bg-gray-50 rounded-lg px-3 py-2">
                <Sheet class="h-4 w-4 shrink-0" />
                Excel file selected — column preview not available. Upload to inspect schema.
              </div>

              <UiButton type="submit" class="w-full" :loading="uploadingDataset" :disabled="!datasetFile">
                Upload Dataset
              </UiButton>
              <div v-if="uploadingDataset" class="w-full mt-2">
                <div class="flex items-center justify-between text-xs text-gray-500 mb-1">
                  <span>{{ datasetUploadProgress >= 100 ? 'Processing file...' : 'Uploading...' }}</span>
                  <span v-if="datasetUploadProgress < 100">{{ datasetUploadProgress }}%</span>
                </div>
                <div class="h-1.5 w-full bg-gray-200 dark:bg-neutral-700 rounded-full overflow-hidden">
                  <div
                    v-if="datasetUploadProgress < 100"
                    class="h-full bg-gray-900 dark:bg-gray-100 rounded-full transition-all duration-200 ease-out"
                    :style="{ width: `${datasetUploadProgress}%` }"
                  />
                  <div
                    v-else
                    class="h-full w-full bg-gray-900 dark:bg-gray-100 rounded-full animate-pulse"
                  />
                </div>
              </div>
            </form>
          </template>

          <!-- Dataset view (editing existing dataset) -->
          <template v-else-if="isDatasetConnection && editingConnection">
            <div class="space-y-4">
              <div>
                <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">Dataset Name</label>
                <p class="text-sm text-gray-900 mt-0.5">{{ editingConnection.name }}</p>
              </div>
              <div v-if="editingConnection.source_filename">
                <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">Source File</label>
                <p class="text-sm text-gray-900 mt-0.5 font-mono">{{ editingConnection.source_filename }}</p>
              </div>
            </div>
            <div class="border-t border-gray-200 pt-4 mt-6 hidden md:block">
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-sm font-medium text-gray-900">Delete this dataset</p>
                  <p class="text-xs text-gray-500">This action cannot be undone.</p>
                </div>
                <UiButton variant="danger" size="sm" @click="openDeleteDialog(editingConnection!)">
                  <Trash2 class="h-3.5 w-3.5" />
                  Delete
                </UiButton>
              </div>
            </div>
          </template>

          <!-- Standard database connection form -->
          <template v-else>
          <form @submit.prevent="handleFormSubmit" class="space-y-4">
            <UiInput
              v-model="form.name"
              label="Connection Name"
              placeholder="My Database"
              required
              :error="formErrors.name"
            />

            <UiInput
              v-model="form.host"
              label="Host"
              placeholder="localhost"
              required
              :error="formErrors.host"
            />

            <div class="grid grid-cols-2 gap-4">
              <UiInput
                v-model="form.database"
                label="Database Name"
                placeholder="mydb"
                required
                :error="formErrors.database"
              />
              <UiInput
                v-model="form.port"
                label="Port"
                type="number"
                :placeholder="String(getConnectorType(form.db_type)?.default_port ?? '')"
                required
                :error="formErrors.port"
              />
            </div>

            <div class="grid grid-cols-2 gap-4">
              <UiInput
                v-model="form.username"
                label="Username"
                placeholder="postgres"
                required
                :error="formErrors.username"
              />
              <UiInput
                v-model="form.password"
                label="Password"
                type="password"
                :placeholder="editingConnection ? 'Leave blank to keep current' : 'password'"
                :required="!editingConnection"
                :hint="editingConnection ? 'Leave blank to keep current password' : undefined"
                :error="formErrors.password"
              />
            </div>

            <!-- SSL Configuration -->
            <div class="border-t pt-4">
              <div class="flex items-center justify-between mb-3">
                <label class="text-sm font-normal text-gray-900">SSL Connection</label>
                <button
                  type="button"
                  @click="form.ssl_enabled = !form.ssl_enabled"
                  class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
                  :class="form.ssl_enabled ? 'bg-blue-600' : 'bg-gray-200'"
                >
                  <span
                    class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                    :class="form.ssl_enabled ? 'translate-x-6' : 'translate-x-1'"
                  />
                </button>
              </div>

              <div v-if="form.ssl_enabled" class="space-y-3">
                <div>
                  <label class="text-sm text-gray-600 mb-1 block">CA Certificate (PEM)</label>
                  <textarea
                    v-model="form.ssl_ca_cert"
                    placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----"
                    rows="6"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-xs focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p class="text-xs text-gray-500 mt-1">
                    <template v-if="editingConnection && editingConnection.has_ssl_ca_cert">
                      A CA certificate is already stored. Leave blank to keep current, or paste a new one to replace it.
                    </template>
                    <template v-else>
                      Optional: Paste your CA certificate for server verification. Leave blank for basic SSL encryption.
                    </template>
                  </p>
                </div>
              </div>
            </div>
          </form>

          <div v-if="editingConnection" class="border-t border-gray-200 pt-4 mt-6">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm font-medium text-gray-900">Delete this connection</p>
                <p class="text-xs text-gray-500">This action cannot be undone.</p>
              </div>
              <UiButton variant="danger" size="sm" @click="openDeleteDialog(editingConnection!)">
                <Trash2 class="h-3.5 w-3.5" />
                Delete
              </UiButton>
            </div>
          </div>
          </template><!-- end v-else standard form -->
        </div>

        <!-- 60% schema panel -->
        <div class="w-full md:w-3/5 border-t md:border-t-0 md:border-l border-gray-200 pt-4 md:pt-0 md:pl-6 flex flex-col gap-3 overflow-hidden">
          <div v-if="!editingConnection" class="flex items-center gap-2 text-sm text-gray-400">
            <Database class="h-4 w-4" />
            <span v-if="isFileUploadConnection">Upload the file to explore its schema.</span>
            <span v-else>Save the connection to explore its schema.</span>
          </div>
          <template v-else>
            <!-- Header -->
            <div class="flex items-center gap-2 shrink-0">
              <h3 class="text-sm font-medium text-gray-900">Database Schema</h3>
              <span v-if="schema" class="text-xs text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded-full">
                {{ schema.table_names.length }} tables
              </span>
            </div>

            <!-- Loading state -->
            <div v-if="schemaLoading" class="space-y-2 shrink-0">
              <UiSkeleton class="h-5 w-full" />
              <UiSkeleton class="h-5 w-5/6" />
              <UiSkeleton class="h-5 w-4/6" />
            </div>

            <!-- Error state -->
            <div v-else-if="schemaError" class="text-sm text-red-500 shrink-0">
              {{ schemaError }}
            </div>

            <!-- No schema yet -->
            <div v-else-if="!schema" class="flex items-center gap-2 text-sm text-gray-400 shrink-0">
              <Database class="h-4 w-4" />
              Click "Refresh Schema" to discover database structure.
            </div>

            <!-- Schema tree -->
            <template v-else>
              <!-- Search -->
              <div class="relative shrink-0">
                <Search class="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-gray-400" />
                <input
                  v-model="schemaSearch"
                  type="text"
                  placeholder="Filter tables..."
                  class="w-full pl-8 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <!-- Tree -->
              <div class="overflow-y-auto flex-1 space-y-1">
                <div v-for="(schemaData, schemaName) in filteredSchemas" :key="schemaName">
                  <!-- Schema row -->
                  <button
                    @click="toggleSchema(String(schemaName))"
                    class="flex items-center gap-1.5 w-full text-left py-1 px-2 rounded hover:bg-gray-50"
                  >
                    <component :is="expandedSchemas[String(schemaName)] ? ChevronDown : ChevronRight" class="h-3.5 w-3.5 text-gray-400 shrink-0" />
                    <Database class="h-3.5 w-3.5 text-gray-500 shrink-0" />
                    <span class="text-xs font-medium text-gray-700 truncate">{{ schemaName }}</span>
                    <span class="text-xs text-gray-400 ml-auto shrink-0">{{ Object.keys(schemaData.tables).length }}</span>
                  </button>

                  <!-- Tables -->
                  <div v-if="expandedSchemas[String(schemaName)]" class="ml-4 space-y-0.5">
                    <div v-for="(tableData, tableName) in schemaData.tables" :key="tableName">
                      <!-- Table row -->
                      <button
                        @click="toggleTable(`${schemaName}.${tableName}`)"
                        class="flex items-center gap-1.5 w-full text-left py-1 px-2 rounded hover:bg-gray-50"
                      >
                        <component :is="expandedTables[`${schemaName}.${tableName}`] ? ChevronDown : ChevronRight" class="h-3.5 w-3.5 text-gray-400 shrink-0" />
                        <Table2 class="h-3.5 w-3.5 text-blue-500 shrink-0" />
                        <span class="text-xs text-gray-700 truncate">{{ tableName }}</span>
                        <span v-if="tableData.row_count != null" class="text-xs text-gray-400 ml-auto shrink-0">{{ tableData.row_count.toLocaleString() }}</span>
                      </button>

                      <!-- Columns -->
                      <div v-if="expandedTables[`${schemaName}.${tableName}`]" class="ml-6 space-y-0.5">
                        <div
                          v-for="col in tableData.columns"
                          :key="col.name"
                          class="flex items-center gap-1.5 py-0.5 px-2 text-xs"
                        >
                          <Key v-if="col.primary_key" class="h-3 w-3 text-amber-500 shrink-0" />
                          <span v-else class="h-3 w-3 shrink-0" />
                          <span class="text-gray-600 truncate">{{ col.name }}</span>
                          <span class="text-gray-400 bg-gray-100 px-1 py-0.5 rounded font-mono ml-auto shrink-0 text-xs">{{ col.type }}</span>
                          <span v-if="col.nullable" class="text-gray-400 shrink-0">?</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Relationships -->
                <div v-if="schema.relationships.length > 0" class="border-t border-gray-100 pt-3 mt-2">
                  <h4 class="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">Relationships</h4>
                  <div class="space-y-1">
                    <div
                      v-for="rel in schema.relationships"
                      :key="`${rel.from}-${rel.to}`"
                      class="flex items-center gap-1.5 text-xs text-gray-500"
                    >
                      <Link2 class="h-3 w-3 shrink-0" />
                      <span class="font-mono truncate">{{ rel.from }}</span>
                      <span class="shrink-0">→</span>
                      <span class="font-mono truncate">{{ rel.to }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </template>
        </div>

        <!-- Mobile-only delete section (appears after schema) -->
        <div v-if="isFileUploadConnection && editingConnection" class="border-t border-gray-200 pt-4 mt-2 md:hidden">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-900">Delete this dataset</p>
              <p class="text-xs text-gray-500">This action cannot be undone.</p>
            </div>
            <UiButton variant="danger" size="sm" @click="openDeleteDialog(editingConnection!)">
              <Trash2 class="h-3.5 w-3.5" />
              Delete
            </UiButton>
          </div>
        </div>
      </div>
    </UiBottomSheet>

    <!-- Delete Confirmation Dialog -->
    <UiDialog
      v-model:open="showDeleteDialog"
      title="Delete Connection"
      size="sm"
    >
      <p class="text-sm text-gray-600">
        Are you sure you want to delete <strong>{{ deletingConnection?.name }}</strong>?
        This action cannot be undone.
      </p>

      <template #footer>
        <UiButton
          variant="outline"
          @click="showDeleteDialog = false"
        >
          Cancel
        </UiButton>
        <UiButton
          variant="danger"
          :loading="deleting"
          @click="confirmDelete"
        >
          Delete
        </UiButton>
      </template>
    </UiDialog>

    <!-- Facebook Account Picker Bottom Sheet -->
    <UiBottomSheet
      :open="showFacebookAccountPicker"
      @update:open="(v: boolean) => { showFacebookAccountPicker = v }"
      title="Select Ad Account"
    >
      <div class="space-y-4">
        <p class="text-sm text-gray-600">Choose which Facebook Ads account to connect:</p>
        <div class="space-y-2">
          <label
            v-for="account in facebookAccounts"
            :key="account.account_id"
            class="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
            :class="{ 'border-blue-500 bg-blue-50': facebookSelectedAccount === account.account_id }"
          >
            <input
              type="radio"
              :value="account.account_id"
              v-model="facebookSelectedAccount"
              class="text-blue-600"
            />
            <div>
              <p class="text-sm font-medium text-gray-900">{{ account.name }}</p>
              <p class="text-xs text-gray-500">ID: {{ account.account_id }} · {{ account.currency }} · {{ account.timezone_name }}</p>
            </div>
          </label>
        </div>
        <UiButton
          class="w-full"
          :disabled="!facebookSelectedAccount"
          :loading="facebookConnecting"
          @click="handleFacebookAccountSelect"
        >
          Connect Account
        </UiButton>
      </div>
    </UiBottomSheet>
  </div>
</template>

<script setup lang="ts">
import { Database, Plus, RefreshCw, Trash2, ArrowLeft, X, Check, ChevronDown, ChevronRight, Table2, Key, Link2, Search, Sheet, FolderOpen } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { DatabaseConnection, ConnectionFormData, ConnectorType, DatabaseSchema, DatasetUploadResponse } from '~/types/connection'

const api = useApi()

// Icon registry — keyed by connector id
const connectorIcons: Record<string, string> = {
  postgres: `<svg viewBox="0 0 432.071 445.383" xmlns="http://www.w3.org/2000/svg"><g fill="#336791"><path d="M323.205 324.227c2.833-23.601 1.984-27.062 19.563-23.239l4.463.392c13.517.615 31.199-2.174 41.587-7 22.362-10.376 35.622-27.7 13.572-23.148-50.297 10.376-53.755-6.655-53.755-6.655 53.111-78.803 75.313-178.836 56.149-203.322C352.514-5.534 262.036 26.049 260.522 26.869l-.482.089c-9.938-2.062-21.06-3.294-33.554-3.496-22.761-.374-40.032 5.967-53.133 15.904 0 0-161.408-66.498-153.899 83.628 1.597 31.936 45.777 241.655 98.47 178.31 19.259-23.163 37.871-42.748 37.871-42.748 9.242 6.14 20.307 9.272 31.912 8.147l.897-.765c-.281 2.876-.157 5.689.359 9.019-13.572 15.167-9.584 17.83-36.723 23.416-27.457 5.659-11.326 15.734-.797 18.367 12.768 3.193 42.305 7.716 62.268-20.224l-.795 3.188c5.325 4.26 4.965 30.619 5.72 49.452.756 18.834 1.05 36.196 3.86 45.739 2.808 9.54 8.315 33.577 36.2 26.732 23.413-5.736 35.94-20.08 37.448-44.38 1.183-19.093 3.585-25.045 3.507-48.974l2.525-1.812c.029 18.28 2.146 33.381 3.854 47.105 1.707 13.725 9.166 26.379 26.988 33.04 25.011 9.362 40.544-4.25 43.141-13.351 2.598-9.101 4.725-25.13 2.017-41.794-2.708-16.665-2.976-27.017-2.976-27.017s5.029-6.461 4.382-30.619c-.647-24.158-1.183-38.447 7.525-50.175l-.256.021z"/></g></svg>`,
  mysql: `<svg viewBox="0 0 256 252" xmlns="http://www.w3.org/2000/svg"><path fill="#00546B" d="M235.648 194.212c-13.918-.347-24.705 1.045-33.752 4.872-2.61 1.043-6.786 1.044-7.134 4.35 1.392 1.392 1.566 3.654 2.784 5.567 2.09 3.479 5.741 8.177 9.047 10.614 3.653 2.783 7.308 5.566 11.134 8.002 6.786 4.176 14.442 6.611 21.053 10.787 3.829 2.434 7.654 5.568 11.482 8.177 1.914 1.39 3.131 3.654 5.568 4.523v-.521c-1.219-1.567-1.567-3.828-2.784-5.568-1.738-1.74-3.48-3.306-5.221-5.046-5.048-6.784-11.308-12.7-18.093-17.571-5.396-3.83-17.75-9.047-20.008-15.485 0 0-.175-.173-.348-.347 3.827-.348 8.35-1.566 12.005-2.436 5.912-1.565 11.308-1.217 17.398-2.784 2.783-.696 5.567-1.566 8.35-2.436v-1.565c-3.13-3.132-5.392-7.307-8.698-10.265-8.873-7.657-18.617-15.137-28.837-21.055-5.394-3.132-12.005-5.048-17.75-7.654-2.09-.696-5.567-1.566-6.784-3.306-3.133-3.827-4.698-8.699-7.135-13.047-5.04-9.568-9.866-20.184-14.576-30.23-3.13-6.786-5.044-13.572-8.872-19.834-17.92-29.577-37.406-47.497-67.33-65.07-6.438-3.653-14.093-5.219-22.27-7.132-4.348-.175-8.699-.522-13.046-.697-2.784-1.218-5.568-4.523-8.004-6.089C34.006 4.573 8.429-8.996 1.122 8.924c-4.698 11.308 6.96 22.441 10.96 28.143 2.96 4.001 6.786 8.524 8.874 13.046 1.392 3.132 1.566 6.263 2.958 9.569 2.784 7.654 5.221 16.178 8.872 23.311 1.914 3.653 4.001 7.48 6.437 10.786 1.392 2.088 3.827 2.957 4.348 5.915-2.435 3.48-2.61 8.7-4.003 13.049-6.263 19.66-3.826 44.017 5.046 58.457 2.784 4.348 9.395 13.572 18.268 10.091 7.83-3.132 6.09-13.046 8.35-21.75.522-2.09.176-3.48 1.219-4.872v.349c2.436 4.87 4.871 9.569 7.133 14.44 5.394 8.524 14.788 17.398 22.617 23.314 4.177 3.13 7.482 8.524 12.707 10.438v-.523h-.349c-1.044-1.566-2.61-2.261-4.001-3.48-3.131-3.13-6.612-6.958-9.047-10.438-7.306-9.744-13.745-20.357-19.486-31.665-2.784-5.392-5.22-11.308-7.481-16.701-1.045-2.088-1.045-5.22-2.784-6.263-2.61 3.827-6.437 7.133-8.351 11.83-3.304 7.481-3.653 16.702-4.871 26.27-.696.176-.349 0-.697.35-6.089-1.567-8.177-8.005-10.265-13.398-5.22-13.919-6.089-36.363-.175-52.19 1.565-4.176 8.702-17.398 5.915-21.23-1.391-3.654-6.263-5.742-8.872-8.525-2.959-3.477-6.088-7.829-8.004-11.83-4.697-10.264-6.96-21.75-11.833-32.015-2.262-4.871-6.263-9.744-9.57-14.093-3.653-4.872-7.829-8.351-10.788-14.268-1.043-2.088-2.436-5.046-1.218-7.133.173-1.74 1.044-2.611 2.784-3.131 2.784-1.218 10.613 1.044 13.398 2.09 7.482 2.434 13.572 4.871 19.834 8.699 2.958 1.913 6.088 5.568 9.742 6.612h4.35c6.787 1.566 14.267.522 20.707 2.09 11.485 2.958 21.75 7.654 31.665 12.7 30.23 15.66 54.762 37.929 71.68 66.506 2.436 4.175 3.48 8.003 5.566 12.354 4.175 8.7 9.396 17.574 13.572 26.097 4.348 8.872 8.699 17.75 14.093 25.402 2.959 4.001 14.787 6.09 20.008 8.177 3.827 1.567 9.918 3.132 13.572 5.046 6.787 3.48 13.398 7.481 19.834 11.308 3.305 1.914 13.572 6.09 14.268 10.265z"/></svg>`,
  dataset: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="3" width="18" height="18" rx="2" stroke="#6B7280" stroke-width="1.5"/><path d="M3 8h18" stroke="#6B7280" stroke-width="1.5"/><path d="M3 13h18" stroke="#6B7280" stroke-width="1.5"/><path d="M3 18h18" stroke="#6B7280" stroke-width="1.5"/><path d="M8 3v18" stroke="#6B7280" stroke-width="1.5"/><path d="M13 3v18" stroke="#6B7280" stroke-width="1.5"/></svg>`,
  facebook_ads: `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M24 12c0-6.627-5.373-12-12-12S0 5.373 0 12c0 5.99 4.388 10.954 10.125 11.854V15.47H7.078V12h3.047V9.356c0-3.007 1.792-4.668 4.533-4.668 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.875V12h3.328l-.532 3.47h-2.796v8.385C19.612 22.954 24 17.99 24 12" fill="#1877F2"/></svg>`,
  sqlite: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C8.13 2 5 3.79 5 6v12c0 2.21 3.13 4 7 4s7-1.79 7-4V6c0-2.21-3.13-4-7-4z" stroke="#0F80CC" stroke-width="1.5" fill="none"/><path d="M5 6c0 2.21 3.13 4 7 4s7-1.79 7-4" stroke="#0F80CC" stroke-width="1.5"/><path d="M5 12c0 2.21 3.13 4 7 4s7-1.79 7-4" stroke="#0F80CC" stroke-width="1.5"/></svg>`,
}

// State
const connections = ref<DatabaseConnection[]>([])
const connectorTypes = ref<ConnectorType[]>([])
const loading = ref(true)
const showTypePicker = ref(false)
const showFormSheet = ref(false)
const editingConnection = ref<DatabaseConnection | null>(null)
const form = ref<ConnectionFormData>({
  name: '',
  db_type: '',
  host: '',
  port: 0,
  database: '',
  username: '',
  password: '',
  ssl_enabled: false,
  ssl_ca_cert: ''
})
const formErrors = ref<Partial<Record<keyof ConnectionFormData, string>>>({})
const saving = ref(false)
const showDeleteDialog = ref(false)
const deletingConnection = ref<DatabaseConnection | null>(null)
const deleting = ref(false)
const refreshingId = ref<number | null>(null)
const testing = ref(false)
const testSuccess = ref(false)

// Schema state
const schema = ref<DatabaseSchema | null>(null)
const schemaLoading = ref(false)
const schemaError = ref<string | null>(null)

// Profiling state
const reprofilingId = ref<number | null>(null)
const profilingPollers = ref<Record<number, ReturnType<typeof setInterval>>>({})

const schemaSearch = ref('')
const expandedSchemas = ref<Record<string, boolean>>({})
const expandedTables = ref<Record<string, boolean>>({})

// Dataset upload state
const datasetFile = ref<File | null>(null)
const datasetDragOver = ref(false)
const datasetFileInputRef = ref<HTMLInputElement | null>(null)
const uploadingDataset = ref(false)
const datasetUploadProgress = ref(0)
const datasetForm = ref({ name: '' })
const datasetFormErrors = ref<{ name?: string; file?: string }>({})
const datasetPreviewColumns = ref<Array<{ name: string; type: string }>>([])

// SQLite upload state
const sqliteFile = ref<File | null>(null)
const sqliteDragOver = ref(false)
const sqliteFileInputRef = ref<HTMLInputElement | null>(null)
const uploadingSqlite = ref(false)
const sqliteForm = ref({ name: '' })
const sqliteFormErrors = ref<{ name?: string; file?: string }>({})
const sqliteUploadResult = ref<{ table_count: number; tables: Array<{ name: string; row_count: number; column_count: number }> } | null>(null)

// Dataset grouping state
const expandedGroups = ref<Record<string, boolean>>({})

// Facebook OAuth state
const facebookOAuthLoading = ref(false)
const facebookAccounts = ref<any[]>([])
const facebookTokenRef = ref('')
const showFacebookAccountPicker = ref(false)
const facebookSelectedAccount = ref('')
const facebookConnecting = ref(false)

interface DatasetGroup {
  fingerprint: string
  name: string
  connections: DatabaseConnection[]
}

// Computed: group dataset connections by schema_fingerprint
const datasetGroups = computed<DatasetGroup[]>(() => {
  const fingerMap = new Map<string, DatabaseConnection[]>()
  for (const conn of connections.value) {
    if (conn.db_type === 'dataset' && conn.schema_fingerprint) {
      const existing = fingerMap.get(conn.schema_fingerprint) || []
      existing.push(conn)
      fingerMap.set(conn.schema_fingerprint, existing)
    }
  }
  // Only groups with 2+ datasets
  const groups: DatasetGroup[] = []
  for (const [fingerprint, conns] of fingerMap) {
    if (conns.length >= 2) {
      groups.push({
        fingerprint,
        name: conns[0].name,
        connections: conns,
      })
    }
  }
  return groups
})

// Computed: connections not in any group
const groupedIds = computed(() => {
  const ids = new Set<number>()
  for (const group of datasetGroups.value) {
    for (const conn of group.connections) {
      ids.add(conn.id)
    }
  }
  return ids
})

const ungroupedConnections = computed(() => {
  return connections.value.filter(c => !groupedIds.value.has(c.id))
})

function toggleGroup(fingerprint: string) {
  expandedGroups.value[fingerprint] = !expandedGroups.value[fingerprint]
}

// Helpers
function getConnectorType(id: string): ConnectorType | undefined {
  return connectorTypes.value.find(t => t.id === id)
}

const isDatasetConnection = computed(() => {
  return form.value.db_type === 'dataset' || editingConnection.value?.db_type === 'dataset'
})

const isSqliteConnection = computed(() => {
  return form.value.db_type === 'sqlite' || editingConnection.value?.db_type === 'sqlite'
})

const isFileUploadConnection = computed(() => {
  return isDatasetConnection.value || isSqliteConnection.value
})

// Computed
const typePickerTitle = computed(() => {
  return 'Choose a Database'
})

const filteredSchemas = computed(() => {
  if (!schema.value) return {}
  const search = schemaSearch.value.toLowerCase()
  if (!search) return schema.value.schemas
  const result: Record<string, any> = {}
  for (const [schemaName, schemaData] of Object.entries(schema.value.schemas)) {
    const filteredTables: Record<string, any> = {}
    for (const [tableName, tableData] of Object.entries(schemaData.tables)) {
      if (tableName.toLowerCase().includes(search)) {
        filteredTables[tableName] = tableData
      }
    }
    if (Object.keys(filteredTables).length > 0) {
      result[schemaName] = { ...schemaData, tables: filteredTables }
    }
  }
  return result
})

// Fetch data on mount
onMounted(async () => {
  await Promise.all([fetchConnections(), fetchConnectorTypes()])
})

// Clean up polling on unmount
onUnmounted(() => {
  stopAllProfilingPolling()
})

// Actions
async function fetchConnections() {
  try {
    loading.value = true
    const response = await api.connections.list() as DatabaseConnection[]
    connections.value = response
    // Start polling for any connections with active profiling
    startPollingForActiveConnections()
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to fetch connections')
  } finally {
    loading.value = false
  }
}

async function fetchConnectorTypes() {
  try {
    const response = await api.connections.getTypes() as ConnectorType[]
    connectorTypes.value = response
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to fetch connector types')
  }
}

async function fetchSchema(connectionId: number) {
  try {
    schemaLoading.value = true
    schemaError.value = null
    schema.value = await api.connections.getSchema(String(connectionId)) as DatabaseSchema
    // Auto-expand the first schema
    if (schema.value) {
      const schemaNames = Object.keys(schema.value.schemas)
      if (schemaNames.length === 1) {
        expandedSchemas.value[schemaNames[0]] = true
      }
    }
  } catch (err: any) {
    if (err?.status === 404 || err?.statusCode === 404) {
      schema.value = null
    } else {
      schemaError.value = err?.data?.detail || err?.message || 'Failed to load schema'
    }
  } finally {
    schemaLoading.value = false
  }
}

// Profiling polling
function startProfilingPolling(connectionId: number) {
  // Don't start duplicate pollers
  if (profilingPollers.value[connectionId]) return

  profilingPollers.value[connectionId] = setInterval(async () => {
    try {
      const status = await api.connections.getProfilingStatus(connectionId) as {
        profiling_status: string
        profiling_progress: string | null
        profiling_error: string | null
      }

      // Update the connection in local state
      const conn = connections.value.find(c => c.id === connectionId)
      if (conn) {
        conn.profiling_status = status.profiling_status as DatabaseConnection['profiling_status']
        conn.profiling_progress = status.profiling_progress
        conn.profiling_error = status.profiling_error
      }

      // Also update editingConnection if it matches
      if (editingConnection.value?.id === connectionId) {
        editingConnection.value.profiling_status = status.profiling_status as DatabaseConnection['profiling_status']
        editingConnection.value.profiling_progress = status.profiling_progress
        editingConnection.value.profiling_error = status.profiling_error
      }

      // Stop polling when terminal state reached
      if (status.profiling_status === 'ready' || status.profiling_status === 'failed') {
        stopProfilingPolling(connectionId)
      }
    } catch {
      // Silently ignore polling errors
    }
  }, 3000)
}

function stopProfilingPolling(connectionId: number) {
  if (profilingPollers.value[connectionId]) {
    clearInterval(profilingPollers.value[connectionId])
    delete profilingPollers.value[connectionId]
  }
}

function stopAllProfilingPolling() {
  for (const id of Object.keys(profilingPollers.value)) {
    clearInterval(profilingPollers.value[Number(id)])
  }
  profilingPollers.value = {}
}

function startPollingForActiveConnections() {
  for (const conn of connections.value) {
    if (conn.profiling_status === 'pending' || conn.profiling_status === 'in_progress') {
      startProfilingPolling(conn.id)
    }
  }
}

async function handleReprofile(connection: DatabaseConnection) {
  try {
    reprofilingId.value = connection.id
    await api.connections.reprofile(connection.id)
    toast.success('Re-profiling started')

    // Update local state to in_progress
    const conn = connections.value.find(c => c.id === connection.id)
    if (conn) {
      conn.profiling_status = 'pending'
      conn.profiling_progress = null
      conn.profiling_error = null
    }
    if (editingConnection.value?.id === connection.id) {
      editingConnection.value.profiling_status = 'pending'
      editingConnection.value.profiling_progress = null
      editingConnection.value.profiling_error = null
    }

    // Start polling
    startProfilingPolling(connection.id)
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to start re-profiling')
  } finally {
    reprofilingId.value = null
  }
}

function toggleSchema(name: string) {
  expandedSchemas.value[name] = !expandedSchemas.value[name]
}

function toggleTable(key: string) {
  expandedTables.value[key] = !expandedTables.value[key]
}

function handleTypePickerClose(value: boolean) {
  showTypePicker.value = value
}

function selectConnectorType(typeId: string) {
  if (typeId === 'facebook_ads') {
    showTypePicker.value = false
    handleFacebookOAuth()
    return
  }
  const type = getConnectorType(typeId)
  form.value.db_type = typeId
  form.value.port = type?.default_port ?? 0
  form.value.ssl_enabled = false
  form.value.ssl_ca_cert = ''
  // Reset dataset and sqlite state when switching types
  clearDatasetFile()
  datasetForm.value = { name: '' }
  datasetFormErrors.value = {}
  clearSqliteFile()
  sqliteForm.value = { name: '' }
  sqliteFormErrors.value = {}
  // Close type picker first to avoid HeadlessUI focus trap conflict
  showTypePicker.value = false
  showFormSheet.value = true
}

function goBackToTypePicker() {
  showFormSheet.value = false
  showTypePicker.value = true
}

function handleFormSheetClose(value: boolean) {
  if (value === false) {
    testSuccess.value = false
    // If creating, go back to type picker
    // If editing, close form sheet
    if (!editingConnection.value) {
      goBackToTypePicker()
    } else {
      showFormSheet.value = false
    }
  }
}

// Facebook OAuth flow
async function handleFacebookOAuth() {
  facebookOAuthLoading.value = true
  // Open popup immediately (before await) to avoid popup blocker
  const popup = window.open('about:blank', 'facebook-oauth', 'width=600,height=700,scrollbars=yes')

  try {
    const { url } = await api.facebookAds.getAuthUrl()
    if (popup) {
      popup.location.href = url
    }

    const handler = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return
      if (event.data?.type !== 'facebook-oauth-callback') return

      window.removeEventListener('message', handler)

      if (event.data.error) {
        toast.error(event.data.error)
        facebookOAuthLoading.value = false
        return
      }

      facebookAccounts.value = event.data.accounts
      facebookTokenRef.value = event.data.token_ref
      showFacebookAccountPicker.value = true
      facebookOAuthLoading.value = false
    }

    window.addEventListener('message', handler)

    // Detect popup closed without completing
    const pollTimer = setInterval(() => {
      if (popup?.closed) {
        clearInterval(pollTimer)
        window.removeEventListener('message', handler)
        facebookOAuthLoading.value = false
      }
    }, 1000)
  } catch (err: any) {
    popup?.close()
    toast.error(err?.message || 'Failed to start Facebook login')
    facebookOAuthLoading.value = false
  }
}

async function handleFacebookAccountSelect() {
  const account = facebookAccounts.value.find((a: any) => a.account_id === facebookSelectedAccount.value)
  if (!account) return

  facebookConnecting.value = true
  try {
    await api.facebookAds.connect(facebookTokenRef.value, account.account_id, account.name)
    toast.success('Facebook Ads account connected!')
    showFacebookAccountPicker.value = false
    facebookAccounts.value = []
    facebookTokenRef.value = ''
    facebookSelectedAccount.value = ''
    await fetchConnections()
  } catch (err: any) {
    toast.error(err?.data?.detail || err?.message || 'Failed to connect account')
  } finally {
    facebookConnecting.value = false
  }
}

function openCreateDialog() {
  editingConnection.value = null
  form.value = {
    name: '',
    db_type: '',
    host: '',
    port: 0,
    database: '',
    username: '',
    password: '',
    ssl_enabled: false,
    ssl_ca_cert: ''
  }
  formErrors.value = {}
  testSuccess.value = false
  clearDatasetFile()
  datasetForm.value = { name: '' }
  datasetFormErrors.value = {}
  clearSqliteFile()
  sqliteForm.value = { name: '' }
  sqliteFormErrors.value = {}
  showTypePicker.value = true
}

function getFormTitle(): string {
  if (editingConnection.value) {
    return editingConnection.value.db_type === 'dataset' ? 'Dataset' : 'Edit Connection'
  }
  const typeName = getConnectorType(form.value.db_type)?.display_name || form.value.db_type
  return `New ${typeName} Connection`
}

function openEditDialog(connection: DatabaseConnection) {
  editingConnection.value = connection
  form.value = {
    name: connection.name,
    db_type: connection.db_type,
    host: connection.host,
    port: connection.port,
    database: connection.database,
    username: connection.username,
    password: '', // Blank by default
    ssl_enabled: connection.ssl_enabled,
    ssl_ca_cert: '' // Never pre-fill cert content
  }
  formErrors.value = {}
  testSuccess.value = false
  // Reset schema state
  schema.value = null
  schemaError.value = null
  schemaSearch.value = ''
  expandedSchemas.value = {}
  expandedTables.value = {}
  // Edit skips type picker, opens form sheet directly
  showFormSheet.value = true
  // Fetch schema in background
  fetchSchema(connection.id)
}

function validateForm(): boolean {
  formErrors.value = {}
  let isValid = true

  if (!form.value.name.trim()) {
    formErrors.value.name = 'Connection name is required'
    isValid = false
  }

  // Skip DB-specific validation for dataset connections
  if (form.value.db_type === 'dataset') {
    return isValid
  }

  if (!form.value.host.trim()) {
    formErrors.value.host = 'Host is required'
    isValid = false
  }

  if (!form.value.port || form.value.port < 1 || form.value.port > 65535) {
    formErrors.value.port = 'Valid port is required (1-65535)'
    isValid = false
  }

  if (!form.value.database.trim()) {
    formErrors.value.database = 'Database name is required'
    isValid = false
  }

  if (!form.value.username.trim()) {
    formErrors.value.username = 'Username is required'
    isValid = false
  }

  if (!editingConnection.value && !form.value.password) {
    formErrors.value.password = 'Password is required'
    isValid = false
  }

  return isValid
}

async function handleFormSubmit() {
  if (!validateForm()) return

  try {
    saving.value = true

    // Build payload
    const payload: any = {
      name: form.value.name,
      db_type: form.value.db_type,
      host: form.value.host,
      port: Number(form.value.port),
      database: form.value.database,
      username: form.value.username,
      ssl_enabled: form.value.ssl_enabled
    }

    // Only include password if it's provided (for edits, empty password = keep current)
    if (form.value.password) {
      payload.password = form.value.password
    }

    // Handle SSL cert: include if provided, or send null to clear if SSL is disabled
    if (form.value.ssl_enabled && form.value.ssl_ca_cert.trim()) {
      payload.ssl_ca_cert = form.value.ssl_ca_cert.trim()
    } else if (!form.value.ssl_enabled) {
      payload.ssl_ca_cert = null
    }

    if (editingConnection.value) {
      await api.connections.update(String(editingConnection.value.id), payload)
      toast.success('Connection updated successfully')
    } else {
      await api.connections.create(payload)
      toast.success('Connection created successfully')
    }

    // Close both sheets
    showFormSheet.value = false
    showTypePicker.value = false
    await fetchConnections()
  } catch (err: any) {
    const errorMessage = err?.data?.detail || err?.message || 'Failed to save connection'
    toast.error(errorMessage)
  } finally {
    saving.value = false
  }
}

async function handleTestConnection() {
  if (!validateForm()) return

  try {
    testing.value = true

    let response: { success: boolean; message: string }

    if (editingConnection.value) {
      // Use saved connection's stored credentials
      response = await api.connections.test(String(editingConnection.value.id)) as { success: boolean; message: string }
    } else {
      const payload: any = {
        name: form.value.name,
        db_type: form.value.db_type,
        host: form.value.host,
        port: Number(form.value.port),
        database: form.value.database,
        username: form.value.username,
        password: form.value.password,
        ssl_enabled: form.value.ssl_enabled
      }

      if (form.value.ssl_enabled && form.value.ssl_ca_cert.trim()) {
        payload.ssl_ca_cert = form.value.ssl_ca_cert.trim()
      }

      response = await api.connections.testUnsaved(payload) as { success: boolean; message: string }
    }

    if (response.success) {
      testSuccess.value = true
      toast.success(response.message || 'Connection test successful')
    } else {
      toast.error(response.message || 'Connection test failed')
    }
  } catch (err: any) {
    const errorMessage = err?.data?.detail || err?.message || 'Connection test failed'
    toast.error(errorMessage)
  } finally {
    testing.value = false
  }
}

async function refreshSchema(connection: DatabaseConnection) {
  try {
    refreshingId.value = connection.id
    await api.connections.refreshSchema(String(connection.id))
    toast.success('Schema refreshed successfully')
    await fetchConnections()
    // Refetch schema to update tree panel
    if (editingConnection.value?.id === connection.id) {
      expandedSchemas.value = {}
      expandedTables.value = {}
      await fetchSchema(connection.id)
    }
  } catch (err: any) {
    const errorMessage = err?.data?.detail || err?.message || 'Failed to refresh schema'
    toast.error(errorMessage)
  } finally {
    refreshingId.value = null
  }
}

function openDeleteDialog(connection: DatabaseConnection) {
  deletingConnection.value = connection
  showDeleteDialog.value = true
}

async function confirmDelete() {
  if (!deletingConnection.value) return

  try {
    deleting.value = true
    await api.connections.delete(String(deletingConnection.value.id))
    toast.success('Connection deleted successfully')
    showDeleteDialog.value = false
    showFormSheet.value = false
    await fetchConnections()
  } catch (err: any) {
    const errorMessage = err?.data?.detail || err?.message || 'Failed to delete connection'
    toast.error(errorMessage)
  } finally {
    deleting.value = false
  }
}

function formatRelativeDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 30) return `${diffDays}d ago`

  return date.toLocaleDateString()
}

// Dataset upload helpers

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function detectColumnType(values: string[]): string {
  const nonEmpty = values.filter(v => v.trim() !== '')
  if (nonEmpty.length === 0) return 'text'
  const allNumbers = nonEmpty.every(v => !isNaN(Number(v)) && v.trim() !== '')
  if (allNumbers) return nonEmpty.some(v => v.includes('.')) ? 'float' : 'integer'
  const datePatterns = [/^\d{4}-\d{2}-\d{2}$/, /^\d{2}\/\d{2}\/\d{4}$/, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/]
  if (nonEmpty.every(v => datePatterns.some(p => p.test(v.trim())))) return 'date'
  return 'text'
}

function parseCsvPreview(text: string): Array<{ name: string; type: string }> {
  const lines = text.split('\n').filter(l => l.trim() !== '')
  if (lines.length === 0) return []
  const headers = lines[0].split(',').map(h => h.trim().replace(/^["']|["']$/g, ''))
  if (headers.length === 0) return []
  const columnSamples: string[][] = headers.map(() => [])
  for (const line of lines.slice(1, 21)) {
    const cells = line.split(',')
    headers.forEach((_, i) => {
      columnSamples[i].push((cells[i] ?? '').trim().replace(/^["']|["']$/g, ''))
    })
  }
  return headers.map((name, i) => ({ name, type: detectColumnType(columnSamples[i]) }))
}

async function applyDatasetFile(file: File) {
  datasetFile.value = file
  datasetPreviewColumns.value = []
  if (!datasetForm.value.name) {
    datasetForm.value.name = file.name.replace(/\.(csv|xlsx)$/i, '')
  }
  if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
    try {
      const text = await file.text()
      datasetPreviewColumns.value = parseCsvPreview(text)
    } catch {
      // Preview is best-effort
    }
  }
}

function clearDatasetFile() {
  datasetFile.value = null
  datasetPreviewColumns.value = []
  if (datasetFileInputRef.value) {
    datasetFileInputRef.value.value = ''
  }
}

function handleDatasetFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) applyDatasetFile(file)
}

function handleDatasetDrop(event: DragEvent) {
  datasetDragOver.value = false
  const file = event.dataTransfer?.files?.[0]
  if (!file) return
  const accepted = ['text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
  const acceptedExts = ['.csv', '.xlsx']
  if (!accepted.includes(file.type) && !acceptedExts.some(ext => file.name.endsWith(ext))) {
    toast.error('Only CSV and Excel (.xlsx) files are accepted')
    return
  }
  applyDatasetFile(file)
}

// SQLite file handling
function applySqliteFile(file: File) {
  sqliteFile.value = file
  sqliteUploadResult.value = null
  if (!sqliteForm.value.name) {
    sqliteForm.value.name = file.name.replace(/\.(sqlite|db)$/i, '')
  }
}

function clearSqliteFile() {
  sqliteFile.value = null
  sqliteUploadResult.value = null
  if (sqliteFileInputRef.value) {
    sqliteFileInputRef.value.value = ''
  }
}

function handleSqliteFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) applySqliteFile(file)
}

function handleSqliteDrop(event: DragEvent) {
  sqliteDragOver.value = false
  const file = event.dataTransfer?.files?.[0]
  if (!file) return
  const acceptedExts = ['.sqlite', '.db']
  if (!acceptedExts.some(ext => file.name.toLowerCase().endsWith(ext))) {
    toast.error('Only .sqlite and .db files are accepted')
    return
  }
  applySqliteFile(file)
}

async function handleSqliteUpload() {
  sqliteFormErrors.value = {}
  if (!sqliteFile.value) {
    sqliteFormErrors.value.file = 'Please select a file to upload'
    return
  }
  try {
    uploadingSqlite.value = true
    const connectionsApi = api.connections as any
    const result = await connectionsApi.uploadSqlite(
      sqliteFile.value,
      sqliteForm.value.name || undefined
    )
    sqliteUploadResult.value = result
    toast.success(`SQLite database "${result.name}" uploaded — ${result.table_count} table(s)`)
    showFormSheet.value = false
    showTypePicker.value = false
    clearSqliteFile()
    sqliteForm.value = { name: '' }
    await fetchConnections()
  } catch (err: any) {
    toast.error(err?.message || 'Upload failed')
  } finally {
    uploadingSqlite.value = false
  }
}

async function handleDatasetUpload() {
  datasetFormErrors.value = {}
  if (!datasetFile.value) {
    datasetFormErrors.value.file = 'Please select a file to upload'
    return
  }
  try {
    uploadingDataset.value = true
    const connectionsApi = api.connections as any
    const result = await connectionsApi.uploadDataset(
      datasetFile.value,
      datasetForm.value.name || undefined,
      (percent: number) => { datasetUploadProgress.value = percent }
    ) as DatasetUploadResponse
    toast.success(`Dataset "${result.name}" uploaded — ${result.row_count.toLocaleString()} rows`)
    showFormSheet.value = false
    showTypePicker.value = false
    clearDatasetFile()
    datasetForm.value = { name: '' }
    await fetchConnections()
  } catch (err: any) {
    toast.error(err?.message || 'Upload failed')
  } finally {
    uploadingDataset.value = false
    datasetUploadProgress.value = 0
  }
}
</script>
