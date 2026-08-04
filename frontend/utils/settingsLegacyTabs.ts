/**
 * Legacy `?tab=` deep links for settings sections that were merged or removed.
 *
 * `users` / `members` / `invitations` and the standalone `org-members` tab were
 * folded into the People page; `org-credits` was removed and its nearest
 * survivor is the account-level Credits section.
 *
 * A target may carry a `sub`, because People resolves its own sub-tab from
 * `?sub=`. Without it a Members bookmark opens People on whichever sub-tab
 * comes first — Active, for a platform admin — which is not what the link meant.
 */
export interface LegacyTabTarget {
  tab: string
  sub?: string
}

const LEGACY_TAB_REDIRECTS: Record<string, LegacyTabTarget> = {
  users: { tab: 'people' },
  invitations: { tab: 'people' },
  members: { tab: 'people', sub: 'members' },
  'org-members': { tab: 'people', sub: 'members' },
  'org-credits': { tab: 'credits' },
}

/** The redirect target for a legacy tab id, or null when the id is current. */
export function resolveLegacyTab(rawTab: string): LegacyTabTarget | null {
  return LEGACY_TAB_REDIRECTS[rawTab] ?? null
}

/**
 * Rewrite a settings query onto the canonical tab, so the address bar stops
 * showing a retired id and the sub-tab actually selects.
 *
 * `sub` is dropped when the target has none: a stale sub from the previous
 * section must not leak onto the new one.
 */
export function canonicalizeTabQuery(
  query: Record<string, unknown>,
  target: LegacyTabTarget,
): Record<string, unknown> {
  const next = { ...query, tab: target.tab }
  if (target.sub) next.sub = target.sub
  else delete next.sub
  return next
}
