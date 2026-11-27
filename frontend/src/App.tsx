import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ChatLayout } from '@/components/layout/ChatLayout'
import { HomePage } from '@/pages/HomePage'
import { ChatPage } from '@/pages/ChatPage'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<ChatLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/c/:conversationId" element={<ChatPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
