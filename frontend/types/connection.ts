export interface ConnectorType {
  id: string
  display_name: string
  description: string
  default_port: number
  badge_variant: string
}

export interface DatabaseConnection {
  id: number
  name: string
  db_type: string
  host: string
  port: number
  database: string
  username: string
  ssl_enabled: boolean
  has_ssl_ca_cert: boolean
  user_id: string
  is_active: boolean
  schema_generated_at: string | null
  table_count: number | null
  created_at: string
  updated_at: string
  source_filename: string | null
  dataset_table_name: string | null
  profiling_status: 'pending' | 'in_progress' | 'ready' | 'failed'
  profiling_progress: string | null
  profiling_error: string | null
}

export interface SchemaColumn {
  name: string
  type: string
  nullable: boolean
  default: string | null
  primary_key: boolean
}

export interface SchemaTable {
  row_count: number | null
  columns: SchemaColumn[]
}

export interface SchemaRelationship {
  from: string
  to: string
}

export interface DatabaseSchema {
  connection_id: number
  connection_name: string
  db_type: string
  generated_at: string
  schemas: Record<string, { tables: Record<string, SchemaTable> }>
  table_names: string[]
  relationships: SchemaRelationship[]
}

export interface ConnectionFormData {
  name: string
  db_type: string
  host: string
  port: number
  database: string
  username: string
  password: string
  ssl_enabled: boolean
  ssl_ca_cert: string
}

export interface ConnectionTestResponse {
  success: boolean
  message: string
  details?: Record<string, any>
}

export interface SqlQueryRequest {
  sql: string
  limit?: number
}

export interface SqlQueryResponse {
  columns: string[]
  rows: any[][]
  row_count: number
  execution_time_ms: number
  truncated: boolean
}

export interface DatasetColumn {
  name: string
  type: string
}

export interface DatasetUploadResponse {
  id: number
  name: string
  source_filename: string
  table_name: string
  row_count: number
  columns: DatasetColumn[]
}
