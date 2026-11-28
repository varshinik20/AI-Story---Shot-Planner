import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { ChatLayout } from '@/components/layout/ChatLayout'
import { StoryForgeLogo } from '@/components/common/StoryForgeLogo'
import { ChatPage } from '@/pages/ChatPage'
import { HomePage } from '@/pages/HomePage'
import { LoginPage } from '@/pages/LoginPage'
import { setUnauthorizedHandler } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'

export function App() {
  const { status, checkSession, handleUnauthorized } = useAuthStore()

  useEffect(() => {
    setUnauthorizedHandler(handleUnauthorized)
    void checkSession()
    return () => {
      setUnauthorizedHandler(null)
    }
  }, [checkSession, handleUnauthorized])

  if (status === 'checking') {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center gap-3 bg-white text-[#212121]">
        <StoryForgeLogo className="h-8 w-8" />
        <div className="flex items-center gap-2 text-sm text-[#6B7280]">
          <Loader2 className="h-4 w-4 animate-spin text-[#10A37F]" />
          <span>Verifying session...</span>
        </div>
      </div>
    )
  }

  if (status !== 'authenticated') {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<LoginPage />} />
        </Routes>
      </BrowserRouter>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<ChatLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/c/:conversationId" element={<ChatPage />} />
          <Route path="/login" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
