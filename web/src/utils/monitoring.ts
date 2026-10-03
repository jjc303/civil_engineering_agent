import type { CameraStatusResponse } from '../types/contract'

// SQLite responses may omit the offset even though these contract fields are UTC.
export function utcDate(value: string | Date) {
  if (value instanceof Date) return value
  return new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`)
}

// Convert the browser's local calendar day to UTC for the existing API contract.
export function todayWindow(now = new Date()) {
  const start = new Date(now)
  start.setHours(0, 0, 0, 0)
  return { start_time_utc: start.toISOString(), end_time_utc: now.toISOString() }
}

export function cameraPage(cameras: CameraStatusResponse[], count: number, page: number, selectedId: string) {
  if (count === 1) return cameras.filter(c => c.camera_id === selectedId).slice(0, 1)
  return cameras.slice((page - 1) * count, page * count)
}

export function cameraSelection(cameras: CameraStatusResponse[], selectedId: string) {
  return cameras.some(c => c.camera_id === selectedId) ? selectedId : cameras[0]?.camera_id ?? ''
}

export function filterCameras(cameras: CameraStatusResponse[], query: string, status: 'all' | 'online' | 'offline') {
  const term = query.trim().toLocaleLowerCase()
  return cameras.filter(camera => {
    const location = typeof camera.extra_details?.location === 'string' ? camera.extra_details.location : ''
    return `${camera.camera_id} ${location}`.toLocaleLowerCase().includes(term)
      && (status === 'all' || camera.is_online === (status === 'online'))
  })
}
