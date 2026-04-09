import { describe, it, expect, vi, beforeEach } from 'vitest'
import { xhrUpload, withAuthRetry } from '~/utils/api/xhrUpload'

// Mock XMLHttpRequest
class MockXHR {
  status = 200
  responseText = ''
  readyState = 0

  private listeners: Record<string, Function[]> = {}
  private uploadListeners: Record<string, Function[]> = {}

  upload = {
    addEventListener: (event: string, fn: Function) => {
      if (!this.uploadListeners[event]) this.uploadListeners[event] = []
      this.uploadListeners[event].push(fn)
    }
  }

  addEventListener(event: string, fn: Function) {
    if (!this.listeners[event]) this.listeners[event] = []
    this.listeners[event].push(fn)
  }

  open = vi.fn()
  send = vi.fn()
  setRequestHeader = vi.fn()

  // Test helpers
  _triggerLoad(status: number, responseText: string) {
    this.status = status
    this.responseText = responseText
    this.listeners['load']?.forEach(fn => fn())
  }

  _triggerError() {
    this.listeners['error']?.forEach(fn => fn())
  }

  _triggerProgress(loaded: number, total: number) {
    this.uploadListeners['progress']?.forEach(fn => fn({ lengthComputable: true, loaded, total }))
  }
}

let mockXhr: MockXHR

beforeEach(() => {
  mockXhr = new MockXHR()
  const MockXHRConstructor = function(this: any) { return mockXhr } as any
  vi.stubGlobal('XMLHttpRequest', MockXHRConstructor)
})

describe('xhrUpload', () => {
  it('resolves with parsed JSON on success', async () => {
    const formData = new FormData()
    const promise = xhrUpload({ url: '/api/test', formData, token: 'tok' })

    mockXhr._triggerLoad(200, JSON.stringify({ id: 1 }))

    await expect(promise).resolves.toEqual({ id: 1 })
    expect(mockXhr.open).toHaveBeenCalledWith('POST', '/api/test')
    expect(mockXhr.setRequestHeader).toHaveBeenCalledWith('Authorization', 'Bearer tok')
  })

  it('rejects with error detail on non-2xx response', async () => {
    const formData = new FormData()
    const promise = xhrUpload({ url: '/api/test', formData, token: null })

    mockXhr._triggerLoad(422, JSON.stringify({ detail: 'Invalid file' }))

    await expect(promise).rejects.toThrow('Invalid file')
  })

  it('rejects with status message when response is not JSON', async () => {
    const formData = new FormData()
    const promise = xhrUpload({ url: '/api/test', formData, token: null })

    mockXhr._triggerLoad(500, 'Internal Server Error')

    await expect(promise).rejects.toThrow('Upload failed with status 500')
  })

  it('rejects on JSON parse failure for success response', async () => {
    const formData = new FormData()
    const promise = xhrUpload({ url: '/api/test', formData, token: null })

    mockXhr._triggerLoad(200, 'not json')

    await expect(promise).rejects.toThrow('Failed to parse response')
  })

  it('rejects on network error', async () => {
    const formData = new FormData()
    const promise = xhrUpload({ url: '/api/test', formData, token: null })

    mockXhr._triggerError()

    await expect(promise).rejects.toThrow('Network error during upload')
  })

  it('reports progress via callback', async () => {
    const onProgress = vi.fn()
    const formData = new FormData()
    const promise = xhrUpload({ url: '/api/test', formData, token: null, onProgress })

    mockXhr._triggerProgress(50, 100)
    mockXhr._triggerProgress(100, 100)
    mockXhr._triggerLoad(200, JSON.stringify({ ok: true }))

    await promise
    expect(onProgress).toHaveBeenCalledWith(50)
    expect(onProgress).toHaveBeenCalledWith(100)
  })

  it('does not set Authorization header when token is null', async () => {
    const formData = new FormData()
    const promise = xhrUpload({ url: '/api/test', formData, token: null })

    mockXhr._triggerLoad(200, '{}')

    await promise
    expect(mockXhr.setRequestHeader).not.toHaveBeenCalled()
  })
})

describe('withAuthRetry', () => {
  it('returns result on first success', async () => {
    const uploadFn = vi.fn().mockResolvedValue({ ok: true })
    const authStore = { token: 'tok1' }

    const result = await withAuthRetry(uploadFn, authStore, {})
    expect(result).toEqual({ ok: true })
    expect(uploadFn).toHaveBeenCalledTimes(1)
    expect(uploadFn).toHaveBeenCalledWith('tok1')
  })

  it('retries with new token on 401 after successful refresh', async () => {
    const error401 = Object.assign(new Error('Unauthorized'), { status: 401 })
    const uploadFn = vi.fn()
      .mockRejectedValueOnce(error401)
      .mockResolvedValueOnce({ ok: true })
    const authStore = {
      token: 'tok1',
      refreshAccessToken: vi.fn().mockImplementation(async () => {
        authStore.token = 'tok2'
        return true
      })
    }

    const result = await withAuthRetry(uploadFn, authStore, {})
    expect(result).toEqual({ ok: true })
    expect(uploadFn).toHaveBeenCalledTimes(2)
    expect(uploadFn).toHaveBeenLastCalledWith('tok2')
  })

  it('redirects to login on 401 when refresh fails', async () => {
    const error401 = Object.assign(new Error('Unauthorized'), { status: 401 })
    const uploadFn = vi.fn().mockRejectedValue(error401)
    const authStore = {
      token: 'tok1',
      refreshAccessToken: vi.fn().mockResolvedValue(false),
      logout: vi.fn().mockResolvedValue(undefined)
    }
    const router = { push: vi.fn().mockResolvedValue(undefined) }

    await expect(withAuthRetry(uploadFn, authStore, router)).rejects.toThrow('Unauthorized')
    expect(authStore.logout).toHaveBeenCalled()
    expect(router.push).toHaveBeenCalledWith('/login')
  })

  it('throws non-401 errors without retrying', async () => {
    const error500 = Object.assign(new Error('Server Error'), { status: 500 })
    const uploadFn = vi.fn().mockRejectedValue(error500)
    const authStore = { token: 'tok1' }

    await expect(withAuthRetry(uploadFn, authStore, {})).rejects.toThrow('Server Error')
    expect(uploadFn).toHaveBeenCalledTimes(1)
  })
})
