import { create } from 'zustand'
import { ApiError, fetchAuthMeApi, loginApi, logoutApi, setCsrfToken } from '@/lib/api'

export type AuthStatus = 'checking' | 'authenticated' | 'unauthenticated'

interface AuthState {
  status: AuthStatus
  username: string | null
  error: string | null
  isSubmitting: boolean

  checkSession: () => Promise<void>
  login: (username: string, password: string) => Promise<boolean>
  logout: () => Promise<void>
  handleUnauthorized: () => void
  clearError: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  status: 'checking',
  username: null,
  error: null,
  isSubmitting: false,

  checkSession: async () => {
    set({ status: 'checking', error: null })
    try {
      const session = await fetchAuthMeApi()
      if (session.authenticated && session.username) {
        set({
          status: 'authenticated',
          username: session.username,
          error: null,
        })
      } else {
        set({
          status: 'unauthenticated',
          username: null,
        })
      }
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Unable to reach the authentication service. Ensure the backend and MongoDB are running.'
      set({
        status: 'unauthenticated',
        username: null,
        error: message,
      })
    }
  },

  login: async (username: string, password: string) => {
    set({ isSubmitting: true, error: null })
    try {
      const result = await loginApi(username.trim(), password)
      set({
        status: 'authenticated',
        username: result.username,
        error: null,
        isSubmitting: false,
      })
      return true
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Unable to sign in right now. Please try again.'
      set({
        status: 'unauthenticated',
        username: null,
        error: message,
        isSubmitting: false,
      })
      return false
    }
  },

  logout: async () => {
    set({ isSubmitting: true, error: null })
    try {
      await logoutApi()
    } finally {
      set({
        status: 'unauthenticated',
        username: null,
        error: null,
        isSubmitting: false,
      })
    }
  },

  handleUnauthorized: () => {
    setCsrfToken(null)
    set({
      status: 'unauthenticated',
      username: null,
      error: 'Your session expired or was signed out. Please log in again.',
    })
  },

  clearError: () => set({ error: null }),
}))
