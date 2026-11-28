import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '@/App'
import { useAuthStore } from '@/store/authStore'

describe('Frontend MongoDB Authentication Gate', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({
      status: 'checking',
      username: null,
      error: null,
      isSubmitting: false,
    })
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('shows LoginPage when unauthenticated, handles invalid & valid login with HttpOnly cookies, restores on refresh, and logs out', async () => {
    let serverAuthenticated = false
    const calls: Array<{ url: string; method: string; credentials?: RequestCredentials; csrf?: string | null }> = []

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method ?? 'GET').toUpperCase()
      const headers = new Headers(init?.headers)
      calls.push({
        url,
        method,
        credentials: init?.credentials,
        csrf: headers.get('X-CSRF-Token'),
      })

      if (url.endsWith('/api/v1/auth/me')) {
        return new Response(
          JSON.stringify(
            serverAuthenticated
              ? {
                  authenticated: true,
                  username: 'studio_director',
                  csrf_token: 'csrf-refreshed-token',
                  expires_at: '2026-11-28T16:00:00Z',
                }
              : { authenticated: false, username: null, csrf_token: null, expires_at: null }
          ),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }

      if (url.endsWith('/api/v1/auth/login') && method === 'POST') {
        const body = JSON.parse(String(init?.body ?? '{}')) as { username?: string; password?: string }
        if (body.username === 'studio_director' && body.password === 'CorrectPass!2026') {
          serverAuthenticated = true
          return new Response(
            JSON.stringify({
              authenticated: true,
              username: 'studio_director',
              csrf_token: 'csrf-login-token',
              expires_at: '2026-11-28T16:00:00Z',
              message: 'Authentication successful.',
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        }
        return new Response(
          JSON.stringify({ error: { code: 'AUTHENTICATION_FAILED', message: 'Invalid username or password.' } }),
          { status: 401, headers: { 'Content-Type': 'application/json' } }
        )
      }

      if (url.endsWith('/api/v1/auth/logout') && method === 'POST') {
        serverAuthenticated = false
        return new Response(
          JSON.stringify({ authenticated: false, message: 'Logged out successfully.' }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }

      return new Response('{}', { status: 404 })
    }) as typeof fetch

    const view = render(<App />)

    // 1. Shows LoginPage when unauthenticated
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in to StoryForge' })).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('Message StoryForge')).not.toBeInTheDocument()

    // 2. Wrong credentials render server error and stay on LoginPage
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'studio_director' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'WrongPassword' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Sign in/i }))
    })
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Invalid username or password.')
    })

    // 3. Valid credentials navigate to chat workspace and never store JWT in localStorage
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'CorrectPass!2026' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Sign in/i }))
    })
    await waitFor(() => {
      expect(screen.getByLabelText('Message StoryForge')).toBeInTheDocument()
    })
    expect(localStorage.length === 0 || !JSON.stringify(localStorage).includes('jwt')).toBe(true)
    expect(calls.every((c) => c.credentials === 'include')).toBe(true)

    // 4. Refresh (unmount + remount) restores authenticated session via GET /api/v1/auth/me
    view.unmount()
    render(<App />)
    await waitFor(() => {
      expect(screen.getByLabelText('Message StoryForge')).toBeInTheDocument()
    })

    // 5. Sign out calls POST /api/v1/auth/logout with CSRF token & returns to LoginPage
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Sign out/i }))
    })
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in to StoryForge' })).toBeInTheDocument()
    })
    const logoutCall = calls.find((c) => c.url.endsWith('/api/v1/auth/logout'))
    expect(logoutCall?.csrf).toBe('csrf-refreshed-token')
  })
})
