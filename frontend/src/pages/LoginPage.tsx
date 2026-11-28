import { useState, type FormEvent } from 'react'
import { AlertCircle, Eye, EyeOff, Loader2, Lock } from 'lucide-react'
import { StoryForgeLogo } from '@/components/common/StoryForgeLogo'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/store/authStore'

export function LoginPage() {
  const { login, error, isSubmitting, clearError } = useAuthStore()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const displayError = localError ?? error

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setLocalError(null)
    clearError()

    if (!username.trim() || !password) {
      setLocalError('Please enter both username and password.')
      return
    }

    await login(username, password)
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#F9F9F9] px-4 py-12 text-[#212121]">
      <div className="w-full max-w-[400px] rounded-2xl border border-[#E5E7EB] bg-white p-7 shadow-sm">
        <div className="flex flex-col items-center text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-[#E5E7EB] bg-[#F9F9F9]">
            <StoryForgeLogo className="h-7 w-7" />
          </div>
          <h1 className="mt-4 text-xl font-semibold tracking-tight text-[#212121]">
            Sign in to StoryForge
          </h1>
          <p className="mt-1 text-sm text-[#6B7280]">
            AI Story &amp; Cinematic Shot Planner
          </p>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
          {displayError && (
            <div
              role="alert"
              className="flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-xs text-red-700"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
              <span>{displayError}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label
              htmlFor="auth-username"
              className="block text-xs font-medium text-[#212121]"
            >
              Username
            </label>
            <input
              id="auth-username"
              name="username"
              type="text"
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(e) => {
                setUsername(e.target.value)
                if (localError) setLocalError(null)
                if (error) clearError()
              }}
              placeholder="Enter authorized username"
              disabled={isSubmitting}
              className="h-10 w-full rounded-xl border border-[#E5E7EB] bg-white px-3.5 text-sm text-[#212121] placeholder:text-[#9CA3AF] focus:border-[#10A37F] focus:outline-none focus:ring-2 focus:ring-[#10A37F]/15 disabled:bg-[#F9F9F9]"
            />
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="auth-password"
              className="block text-xs font-medium text-[#212121]"
            >
              Password
            </label>
            <div className="relative">
              <input
                id="auth-password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value)
                  if (localError) setLocalError(null)
                  if (error) clearError()
                }}
                placeholder="Enter password"
                disabled={isSubmitting}
                className="h-10 w-full rounded-xl border border-[#E5E7EB] bg-white pl-3.5 pr-10 text-sm text-[#212121] placeholder:text-[#9CA3AF] focus:border-[#10A37F] focus:outline-none focus:ring-2 focus:ring-[#10A37F]/15 disabled:bg-[#F9F9F9]"
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-[#6B7280] transition-colors hover:text-[#212121]"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <Button
            type="submit"
            variant="accent"
            disabled={isSubmitting}
            className="h-10 w-full rounded-xl text-sm font-medium"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Verifying...
              </>
            ) : (
              <>
                <Lock className="h-4 w-4" />
                Sign in
              </>
            )}
          </Button>
        </form>

        <p className="mt-5 text-center text-[11px] text-[#6B7280]">
          Protected workspace • Sessions use secure HttpOnly cookies
        </p>
      </div>
    </div>
  )
}
