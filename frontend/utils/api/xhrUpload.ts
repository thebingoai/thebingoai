export interface XhrUploadOptions {
  url: string
  formData: FormData
  token: string | null
  onProgress?: (percent: number) => void
}

export interface UploadError extends Error {
  status?: number
}

export function xhrUpload({ url, formData, token, onProgress }: XhrUploadOptions): Promise<any> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()

    if (onProgress) {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      })
    }

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText))
        } catch (e) {
          reject(new Error('Failed to parse response'))
        }
      } else {
        try {
          const error = JSON.parse(xhr.responseText)
          reject(Object.assign(new Error(error.detail || 'Upload failed'), { status: xhr.status }))
        } catch (e) {
          reject(Object.assign(new Error(`Upload failed with status ${xhr.status}`), { status: xhr.status }))
        }
      }
    })

    xhr.addEventListener('error', () => {
      reject(new Error('Network error during upload'))
    })

    xhr.open('POST', url)
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    }
    xhr.send(formData)
  })
}

export async function withAuthRetry(
  uploadFn: (token: string | null) => Promise<any>,
  authStore: any,
  router: any
): Promise<any> {
  try {
    return await uploadFn(authStore.token)
  } catch (error: any) {
    if (error?.status === 401) {
      const refreshed = await authStore.refreshAccessToken()
      if (refreshed) {
        return await uploadFn(authStore.token)
      } else {
        await authStore.logout()
        await router.push('/login')
      }
    }
    throw error
  }
}
