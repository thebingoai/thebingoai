import {
  Home,
  FileText,
  Search,
  MessageSquare,
  Briefcase,
  Settings,
  type LucideIcon
} from 'lucide-vue-next'

export interface NavItem {
  name: string
  href: string
  icon: LucideIcon
}

export const NAV_ITEMS: NavItem[] = [
  { name: 'Dashboard', href: '/', icon: Home },
  { name: 'Documents', href: '/documents', icon: FileText },
  { name: 'Search', href: '/search', icon: Search },
  { name: 'Chat', href: '/chat', icon: MessageSquare },
  { name: 'Jobs', href: '/jobs', icon: Briefcase },
  { name: 'Settings', href: '/settings', icon: Settings }
]

export const SCORE_THRESHOLDS = {
  EXCELLENT: 0.8,
  GOOD: 0.6,
  FAIR: 0.4
}

export const DEFAULT_VALUES = {
  NAMESPACE: 'default',
  TOP_K: 5,
  TEMPERATURE: 0.7,
  PROVIDER: 'openai' as const
}

export const LIMITS = {
  QUERY_MIN_LENGTH: 1,
  QUERY_MAX_LENGTH: 10000,
  TOP_K_MIN: 1,
  TOP_K_MAX_SEARCH: 100,
  TOP_K_MAX_CHAT: 20,
  TEMPERATURE_MIN: 0.0,
  TEMPERATURE_MAX: 2.0
}

export const MESSAGES = {
  UPLOAD_SUCCESS: 'File uploaded successfully',
  UPLOAD_QUEUED: 'File queued for processing',
  UPLOAD_ERROR: 'Failed to upload file',
  SEARCH_ERROR: 'Search failed',
  CHAT_ERROR: 'Failed to send message',
  CONNECTION_ERROR: 'Failed to connect to backend',
  COPY_SUCCESS: 'Copied to clipboard',
  DELETE_SUCCESS: 'Deleted successfully'
}

export const POLLING_INTERVALS = {
  JOB_STATUS: 2000, // 2 seconds
  HEALTH_CHECK: 30000 // 30 seconds
}
