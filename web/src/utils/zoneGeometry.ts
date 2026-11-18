import type { DangerZoneConfig, SourceResolution } from '@/types/contract'

export type Point2D = [number, number]

export const ZONE_GEOMETRY_CONSTANTS = {
  defaultResolution: { width: 1920, height: 1080 } satisfies SourceResolution,
  fallbackCanvasWidth: 840,
  defaultDwellSeconds: 5.0,
  defaultDebounceFrames: {
    enter_debounce_frames: 3,
    exit_debounce_frames: 5,
    helmet_debounce_frames: 5,
  },
  minPolygonPoints: 3,
  maxZoneIdLength: 128,
  hitRadiusPx: 12,
  anchorRadiusPx: 7,
  gridStepPx: 40,
  pointOffsetPx: 80,
  /** Proportional default polygon in [0..1] normalized coordinates. */
  defaultPolygonRatios: [
    [0.21, 0.23],
    [0.47, 0.19],
    [0.50, 0.65],
    [0.26, 0.69],
  ] as ReadonlyArray<Point2D>,
  canvasPalette: {
    unavailableBg: '#0f172a',
    unavailableGrid: '#1e293b',
    overlayGrid: 'rgba(226, 232, 240, 0.22)',
    inactiveEnabledStroke: '#fb7185',
    inactiveDisabledStroke: '#94a3b8',
    activeFill: 'rgba(239, 68, 68, 0.25)',
    activeStroke: '#ef4444',
    anchorFill: '#facc15',
    anchorStroke: '#000000',
    labelFill: '#ffffff',
    labelFont: '11px sans-serif',
  },
} as const

export function createDefaultPolygon(
  resolution: SourceResolution = ZONE_GEOMETRY_CONSTANTS.defaultResolution,
): Point2D[] {
  return ZONE_GEOMETRY_CONSTANTS.defaultPolygonRatios.map(([rx, ry]) => [
    Math.round(rx * resolution.width),
    Math.round(ry * resolution.height),
  ])
}

export function createDefaultZone(
  index: number,
  zoneName: string,
  resolution: SourceResolution = ZONE_GEOMETRY_CONSTANTS.defaultResolution,
): DangerZoneConfig {
  return {
    zone_id: `zone-${index}`,
    zone_name: zoneName,
    polygon: createDefaultPolygon(resolution),
    enabled: true,
    alarm_dwell_threshold_seconds: ZONE_GEOMETRY_CONSTANTS.defaultDwellSeconds,
  }
}

export function computeCanvasDimensions(
  containerWidth: number,
  resolution: SourceResolution,
): { width: number; height: number } {
  const width = containerWidth > 0 ? containerWidth : ZONE_GEOMETRY_CONSTANTS.fallbackCanvasWidth
  const safeResWidth = resolution.width > 0 ? resolution.width : ZONE_GEOMETRY_CONSTANTS.defaultResolution.width
  const safeResHeight = resolution.height > 0 ? resolution.height : ZONE_GEOMETRY_CONSTANTS.defaultResolution.height
  return {
    width,
    height: (width * safeResHeight) / safeResWidth,
  }
}

export function scalePolygonToResolution(
  polygon: ReadonlyArray<Point2D>,
  from: SourceResolution,
  to: SourceResolution,
): Point2D[] {
  if (!from.width || !from.height || !to.width || !to.height) {
    return polygon.map(([x, y]) => [x, y])
  }
  return polygon.map(([x, y]) => [
    Math.round((x * to.width) / from.width),
    Math.round((y * to.height) / from.height),
  ])
}

export function computeNextPolygonPoint(
  points: ReadonlyArray<Point2D>,
  resolution: SourceResolution,
): Point2D {
  if (points.length === 0) {
    return [Math.round(resolution.width * 0.26), Math.round(resolution.height * 0.46)]
  }
  const last = points[points.length - 1]!
  const offset = ZONE_GEOMETRY_CONSTANTS.pointOffsetPx
  const margin = Math.round(offset / 2)
  return [
    Math.min(last[0] + offset, Math.max(margin, resolution.width - margin)),
    Math.min(last[1] + offset, Math.max(margin, resolution.height - margin)),
  ]
}

export function hitTestPolygonVertex(
  points: ReadonlyArray<Point2D>,
  canvasX: number,
  canvasY: number,
  scaleX: number,
  scaleY: number,
  hitRadiusPx = ZONE_GEOMETRY_CONSTANTS.hitRadiusPx,
): number {
  for (let i = 0; i < points.length; i += 1) {
    const cx = points[i]![0] * scaleX
    const cy = points[i]![1] * scaleY
    if (Math.hypot(canvasX - cx, canvasY - cy) <= hitRadiusPx) {
      return i
    }
  }
  return -1
}

export function canvasPointToSource(
  canvasX: number,
  canvasY: number,
  scaleX: number,
  scaleY: number,
  resolution: SourceResolution,
): Point2D {
  const rawX = scaleX > 0 ? canvasX / scaleX : 0
  const rawY = scaleY > 0 ? canvasY / scaleY : 0
  return [
    Math.round(Math.max(0, Math.min(rawX, resolution.width))),
    Math.round(Math.max(0, Math.min(rawY, resolution.height))),
  ]
}

export interface ZoneSceneRenderParams {
  ctx: CanvasRenderingContext2D
  canvasWidth: number
  canvasHeight: number
  dpr: number
  resolution: SourceResolution
  hasVideoPreview: boolean
  zones: ReadonlyArray<DangerZoneConfig>
  selectedZoneIndex: number
  activePolygon: ReadonlyArray<Point2D>
}

export function drawZoneScene(params: ZoneSceneRenderParams): void {
  const { ctx, canvasWidth, canvasHeight, dpr, resolution, hasVideoPreview, zones, selectedZoneIndex, activePolygon } =
    params
  const palette = ZONE_GEOMETRY_CONSTANTS.canvasPalette

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, canvasWidth, canvasHeight)

  if (!hasVideoPreview) {
    ctx.fillStyle = palette.unavailableBg
    ctx.fillRect(0, 0, canvasWidth, canvasHeight)
  }

  ctx.strokeStyle = hasVideoPreview ? palette.overlayGrid : palette.unavailableGrid
  ctx.lineWidth = 1
  const step = ZONE_GEOMETRY_CONSTANTS.gridStepPx
  for (let x = 0; x < canvasWidth; x += step) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, canvasHeight)
    ctx.stroke()
  }
  for (let y = 0; y < canvasHeight; y += step) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(canvasWidth, y)
    ctx.stroke()
  }

  const scaleX = canvasWidth / resolution.width
  const scaleY = canvasHeight / resolution.height

  for (let index = 0; index < zones.length; index += 1) {
    if (index === selectedZoneIndex) continue
    const zone = zones[index]!
    if (zone.polygon.length < 2) continue
    ctx.beginPath()
    ctx.moveTo(zone.polygon[0]![0] * scaleX, zone.polygon[0]![1] * scaleY)
    zone.polygon.slice(1).forEach((point) => ctx.lineTo(point[0] * scaleX, point[1] * scaleY))
    ctx.closePath()
    ctx.strokeStyle = zone.enabled ? palette.inactiveEnabledStroke : palette.inactiveDisabledStroke
    ctx.lineWidth = 2
    ctx.setLineDash([7, 5])
    ctx.stroke()
    ctx.setLineDash([])
  }

  if (activePolygon.length < 2) return

  ctx.beginPath()
  ctx.moveTo(activePolygon[0]![0] * scaleX, activePolygon[0]![1] * scaleY)
  for (let i = 1; i < activePolygon.length; i += 1) {
    ctx.lineTo(activePolygon[i]![0] * scaleX, activePolygon[i]![1] * scaleY)
  }
  ctx.closePath()

  ctx.fillStyle = palette.activeFill
  ctx.fill()
  ctx.strokeStyle = palette.activeStroke
  ctx.lineWidth = 3
  ctx.stroke()

  for (let i = 0; i < activePolygon.length; i += 1) {
    const cx = activePolygon[i]![0] * scaleX
    const cy = activePolygon[i]![1] * scaleY

    ctx.beginPath()
    ctx.arc(cx, cy, ZONE_GEOMETRY_CONSTANTS.anchorRadiusPx, 0, 2 * Math.PI)
    ctx.fillStyle = palette.anchorFill
    ctx.fill()
    ctx.lineWidth = 2
    ctx.strokeStyle = palette.anchorStroke
    ctx.stroke()

    ctx.fillStyle = palette.labelFill
    ctx.font = palette.labelFont
    ctx.fillText(`P${i + 1}`, cx + 9, cy - 5)
  }
}
