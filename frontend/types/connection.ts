export enum DatabaseType {
  POSTGRES = 'postgres',
  MYSQL = 'mysql'
}

export interface DatabaseConnection {
  id: number
  name: string
  db_type: DatabaseType
  host: string
  port: number
  database: string
  username: string
  ssl_enabled: boolean
  has_ssl_ca_cert: boolean
  user_id: string
  is_active: boolean
  schema_generated_at: string | null
  created_at: string
  updated_at: string
}

export interface ConnectionFormData {
  name: string
  db_type: DatabaseType
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
