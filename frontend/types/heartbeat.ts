export interface HeartbeatJob {
  id: string
  name: string
  prompt: string
  schedule_type: 'preset' | 'cron'
  schedule_value: string
  cron_expression: string
  is_active: boolean
  next_run_at: string | null
  last_run_at: string | null
  created_at: string
  updated_at: string
}

export interface HeartbeatJobRun {
  id: string
  job_id: string
  status: 'running' | 'completed' | 'failed'
  started_at: string
  completed_at: string | null
  prompt: string | null
  response: string | null
  error: string | null
  duration_ms: number | null
}

export interface HeartbeatJobRunListResponse {
  runs: HeartbeatJobRun[]
  total: number
}

export interface HeartbeatJobCreateRequest {
  name: string
  prompt: string
  schedule_type: 'preset' | 'cron'
  schedule_value: string
}

export interface HeartbeatJobUpdateRequest {
  name?: string
  prompt?: string
  schedule_type?: 'preset' | 'cron'
  schedule_value?: string
}

function utcHourToLocalLabel(utcHour: number): string {
  const d = new Date()
  d.setUTCHours(utcHour, 0, 0, 0)
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

const _9amLocal = utcHourToLocalLabel(9)

export const PRESET_OPTIONS = [
  { label: 'Every 5 minutes', value: '5m' },
  { label: 'Every 15 minutes', value: '15m' },
  { label: 'Every 30 minutes', value: '30m' },
  { label: 'Every hour', value: '1h' },
  { label: 'Every 2 hours', value: '2h' },
  { label: 'Every 6 hours', value: '6h' },
  { label: 'Every 12 hours', value: '12h' },
  { label: `Daily (${_9amLocal})`, value: 'daily' },
  { label: `Weekly (Monday ${_9amLocal})`, value: 'weekly' },
  { label: `Weekdays (Mon-Fri ${_9amLocal})`, value: 'weekdays' },
]
