import { useEffect, useRef, useState } from 'react'

type RecognitionEvent = Event & { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }
type Recognition = EventTarget & {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  abort: () => void
  onresult: ((event: RecognitionEvent) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
}
type RecognitionCtor = new () => Recognition

function ctor(): RecognitionCtor | null {
  const win = window as typeof window & { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return win.SpeechRecognition || win.webkitSpeechRecognition || null
}

export function useSpeechCapture(text: string, onText: (value: string) => void) {
  const [listening, setListening] = useState(false)
  const [usedSpeech, setUsedSpeech] = useState(false)
  const ref = useRef<Recognition | null>(null)
  const stable = useRef('')

  useEffect(() => () => ref.current?.abort(), [])

  function start() {
    const Ctor = ctor()
    if (!Ctor || listening) return false
    const engine = new Ctor()
    engine.continuous = true
    engine.interimResults = true
    engine.lang = navigator.language || 'en-US'
    stable.current = text.trim()
    engine.onresult = (event) => {
      let finalText = stable.current
      let interim = ''
      for (let index = 0; index < event.results.length; index += 1) {
        const result = event.results[index]
        const transcript = result[0]?.transcript?.trim() || ''
        if (!transcript) continue
        if (result.isFinal) finalText = `${finalText} ${transcript}`.trim()
        else interim = `${interim} ${transcript}`.trim()
      }
      stable.current = finalText
      onText(`${finalText}${interim ? ` ${interim}` : ''}`.trim())
      setUsedSpeech(true)
    }
    engine.onend = () => setListening(false)
    engine.onerror = () => setListening(false)
    ref.current = engine
    engine.start()
    setListening(true)
    return true
  }

  function stop() {
    ref.current?.stop()
    setListening(false)
  }

  function reset() {
    stable.current = ''
    setUsedSpeech(false)
  }

  return { available: Boolean(ctor()), listening, usedSpeech, start, stop, reset }
}
