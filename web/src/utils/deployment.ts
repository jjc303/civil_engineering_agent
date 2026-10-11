export const appBasePath = import.meta.env.BASE_URL.replace(/\/$/, '')
export const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || appBasePath).replace(/\/$/, '')

export function appPath(path: string): string {
  return `${appBasePath}/${path.replace(/^\/+/, '')}`
}

export function learningPath(publicUrl: string): string | undefined {
  try {
    const path = new URL(publicUrl, window.location.origin).pathname
    const relative = appBasePath && path.startsWith(appBasePath + '/') ? path.slice(appBasePath.length) : path
    return /^\/learn\/[A-Za-z0-9_-]+\/?$/.test(relative) ? appPath(relative) : undefined
  } catch {
    return undefined
  }
}
