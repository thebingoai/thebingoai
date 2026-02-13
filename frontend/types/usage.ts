export interface UsageSummary {
  user_id: string
  period: {
    start: string
    end: string
  }
  totals: {
    operations: number
    tokens: number
    cost: number
  }
  by_operation: Record<string, {
    count: number
    tokens: number
    cost: number
  }>
}

export interface DailyUsage {
  date: string
  tokens: number
  cost: number
  operations: number
}
