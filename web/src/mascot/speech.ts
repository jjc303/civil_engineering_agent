import { MASCOT_DEFAULTS } from './config'

export interface SpeechPort {
  isSupported(): boolean
  speak(text: string, locale: string, onEnd?: () => void): boolean
  stop(): void
}

function normalizeForSpeech(raw: string): string {
  return raw
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/[#>*_~|-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, MASCOT_DEFAULTS.maxSpeechChars)
}

function resolveVoiceLang(locale: string): string {
  return locale === 'zh-HK' ? 'zh-HK' : 'zh-CN'
}

export const webSpeechAdapter: SpeechPort = {
  isSupported(): boolean {
    return (
      typeof window !== 'undefined' &&
      'speechSynthesis' in window &&
      typeof window.SpeechSynthesisUtterance === 'function'
    )
  },

  speak(text: string, locale: string, onEnd?: () => void): boolean {
    if (!this.isSupported()) return false
    const clean = normalizeForSpeech(text)
    if (!clean) return false
    try {
      window.speechSynthesis.cancel()
      const utterance = new window.SpeechSynthesisUtterance(clean)
      utterance.lang = resolveVoiceLang(locale)
      utterance.rate = MASCOT_DEFAULTS.speechRate
      utterance.pitch = MASCOT_DEFAULTS.speechPitch
      if (onEnd) {
        utterance.onend = onEnd
        utterance.onerror = onEnd
      }
      window.speechSynthesis.speak(utterance)
      return true
    } catch {
      return false
    }
  },

  stop(): void {
    if (!this.isSupported()) return
    try {
      window.speechSynthesis.cancel()
    } catch {
      // Ignore synthesis cancellation failures
    }
  },
}

let activeSpeechPort: SpeechPort = webSpeechAdapter

export function getSpeechPort(): SpeechPort {
  return activeSpeechPort
}

export function registerSpeechPort(port: SpeechPort): void {
  activeSpeechPort = port
}

export function resetSpeechPort(): void {
  activeSpeechPort = webSpeechAdapter
}
