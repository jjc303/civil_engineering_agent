export type BrowserStorageKind = 'local' | 'session'

function resolveStorage(kind: BrowserStorageKind): Storage | null {
  if (typeof window === 'undefined') return null
  try {
    return kind === 'local' ? window.localStorage : window.sessionStorage
  } catch {
    return null
  }
}

export function readStorage(key: string, kind: BrowserStorageKind = 'local'): string | null {
  const storage = resolveStorage(kind)
  if (!storage) return null
  try {
    return storage.getItem(key)
  } catch {
    return null
  }
}

export function writeStorage(key: string, value: string, kind: BrowserStorageKind = 'local'): void {
  const storage = resolveStorage(kind)
  if (!storage) return
  try {
    storage.setItem(key, value)
  } catch {
    // Ignore quota or disabled-storage errors
  }
}

export function removeStorage(key: string, kind: BrowserStorageKind = 'local'): void {
  const storage = resolveStorage(kind)
  if (!storage) return
  try {
    storage.removeItem(key)
  } catch {
    // Ignore disabled-storage errors
  }
}

export function readJsonStorage<T>(key: string, kind: BrowserStorageKind = 'session'): T | null {
  const raw = readStorage(key, kind)
  if (!raw) return null
  try {
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

export function writeJsonStorage(key: string, value: unknown, kind: BrowserStorageKind = 'session'): void {
  try {
    writeStorage(key, JSON.stringify(value), kind)
  } catch {
    // Ignore serialization errors
  }
}
