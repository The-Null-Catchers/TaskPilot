import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, request } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('request', () => {
  it('adds JSON and bearer headers for authenticated requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      request<{ ok: boolean }>('/api/v1/example', {
        method: 'POST',
        body: JSON.stringify({ name: 'TaskPilot' }),
      }, 'access-token'),
    ).resolves.toEqual({ ok: true })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = init.headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer access-token')
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(init.credentials).toBe('include')
    expect(init.cache).toBe('no-store')
  })

  it('does not force a content type for FormData uploads', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 'attachment' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const body = new FormData()
    body.append('file', new Blob(['hello']), 'hello.txt')

    await request('/api/v1/attachments', { method: 'POST', body }, 'token')

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = init.headers as Headers
    expect(headers.has('Content-Type')).toBe(false)
  })

  it('surfaces structured API errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { message: 'Access denied' } }), {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )

    try {
      await request('/api/v1/private')
      throw new Error('Expected request to fail')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(403)
      expect((error as ApiError).message).toBe('Access denied')
    }
  })

  it('returns undefined for 204 responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))
    await expect(request('/api/v1/resource', { method: 'DELETE' })).resolves.toBeUndefined()
  })
})
