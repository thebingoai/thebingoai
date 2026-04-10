export function createFacebookAdsApi(fetchWithRefresh: Function) {
  return {
    async getAuthUrl(): Promise<{ url: string }> {
      return fetchWithRefresh('/api/facebook-ads/auth/url', {})
    },
    async connect(
      tokenRef: string,
      accountId: string,
      accountName: string,
    ): Promise<{ connection_id: number; message: string }> {
      return fetchWithRefresh('/api/facebook-ads/auth/connect', {
        method: 'POST',
        body: { token_ref: tokenRef, account_id: accountId, account_name: accountName },
      })
    },
  }
}
