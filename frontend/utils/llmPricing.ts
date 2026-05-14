// Rough USD per 1K input tokens. Mockup-quality estimate, NOT billing.
// Update when providers move pricing.
const PRICE_PER_1K_INPUT: Record<string, number> = {
  'claude-opus-4-7':             0.015,
  'claude-opus-4-6':             0.015,
  'claude-sonnet-4-6':           0.003,
  'claude-3-5-sonnet-20241022':  0.003,
  'claude-haiku-4-5-20251001':   0.0008,
  'claude-3-5-haiku-20241022':   0.0008,
  'gpt-4o':                      0.0025,
  'gpt-4-turbo':                 0.01,
  'gpt-3.5-turbo':               0.0005,
}

const FALLBACK_PRICE = 0.003

export function estimateCallCost(model: string | null | undefined, charCount: number): string {
  const tokens = charCount / 4
  const price = (model && PRICE_PER_1K_INPUT[model]) ?? FALLBACK_PRICE
  return ((tokens / 1000) * price).toFixed(3)
}
