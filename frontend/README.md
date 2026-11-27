# StoryForge Frontend (CINEMIND UI)

ChatGPT-style React 18 + TypeScript + Vite frontend for **StoryForge / CINEMIND**.

---

## Voice Input & Speech-to-Text

The chat composer includes continuous voice dictation built on the browser **Web Speech API** (`window.SpeechRecognition` / `window.webkitSpeechRecognition`):

- **Hook:** `src/hooks/useSpeechRecognition.ts` (isolated state machine: `idle`, `requesting_permission`, `listening`, `stopping`, `completed`, `error`, `unsupported`).
- **Control:** `src/components/chat/VoiceInputButton.tsx` (idle mic icon, live red recording indicator with animated waveform, `"Listening..."` status, `MM:SS` duration, and explicit Stop control).
- **Composer Integration:** `src/components/chat/ChatComposer.tsx` preserves pre-existing typed text, streams interim + final transcription, allows editing after stopping, and **never auto-submits** spoken prompts.
- **Default Language:** Configured to `en-IN` (`DEFAULT_SPEECH_LANGUAGE`) and passable via `speechLanguage` prop for future language-settings integration.

### Browser Compatibility, Privacy & Limitations

- **Supported Browsers:** Best supported in **Google Chrome** and **Microsoft Edge** (desktop). Browsers without `SpeechRecognition` / `webkitSpeechRecognition` (such as Firefox or some mobile WebViews) show a non-blocking alert while typed chat continues working normally.
- **HTTPS / `localhost` Requirement:** Browsers require a secure context (`https://` or `http://localhost`) to grant microphone access.
- **Privacy:** Microphone permission is requested only when clicking the microphone icon. Audio is not stored or uploaded by StoryForge's backend; however, the browser's Web Speech API implementation may route audio through the browser vendor's speech recognition service.
- **Language Support:** Actual available recognition languages depend on the user's browser and OS speech packs.

---

## Scripts (PowerShell)

```powershell
cd frontend
npm install
npm run dev      # Start Vite dev server (http://localhost:5173)
npm run lint     # TypeScript typecheck
npm test         # Run Vitest unit & component tests
npm run build    # Production build
```

### Manual Voice Input Testing Guide (Chrome / Edge)

1. Open http://localhost:5173/ in Google Chrome or Microsoft Edge.
2. Optionally type an opening phrase in the composer (e.g., `"Create a cinematic story about trust."`).
3. Click the **microphone** button (`Start voice input`) and allow microphone permission when prompted.
4. Speak a sentence, pause for 4–5 seconds, and speak a second sentence—verify both sentences accumulate in the composer without cutting off or duplicating text.
5. Click the red **Stop recording** button—verify `"Listening..."` clears, your full text stays editable in the composer, and the message is **not** sent until you click **Send** or press **Enter**.
