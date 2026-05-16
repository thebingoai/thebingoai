// Shared constants for the chat / dataset composables.
// Kept here so that polling cadence, safety timeouts, row caps and the
// "what counts as an image" set don't drift between files.

/** Cadence (ms) for status polls — used by useDatasetStatus + useBriefing. */
export const POLL_INTERVAL_MS = 3000

/**
 * Hard ceiling for waiting on a stream to finish. Matches the Redis TTL on
 * conversation streaming state so a stuck stream eventually unlocks the UI.
 */
export const STREAMING_SAFETY_TIMEOUT_MS = 5 * 60 * 1000

/** Max rows we surface in the chat-bubble's tabular preview of a query result. */
export const MAX_QUERY_RESULT_ROWS = 50

/** MIME types treated as images for attachment preview + presigned URL resolution. */
export const IMAGE_MIME_TYPES: ReadonlySet<string> = new Set([
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
])
