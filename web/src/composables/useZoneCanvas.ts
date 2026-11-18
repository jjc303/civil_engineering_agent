import { computed, nextTick, onBeforeUnmount, ref, type Ref } from 'vue'
import { previewFrameUrl, previewUrl } from '@/api/cameraManagement'
import type { DangerZoneConfig, SourceResolution } from '@/types/contract'
import {
  ZONE_GEOMETRY_CONSTANTS,
  canvasPointToSource,
  computeCanvasDimensions,
  drawZoneScene,
  hitTestPolygonVertex,
  type Point2D,
} from '@/utils/zoneGeometry'

export function useZoneCanvas(params: {
  selectedCameraId: Ref<string>
  sourceResolution: Ref<SourceResolution>
  polygonPoints: Ref<Point2D[]>
  displayZones: Ref<DangerZoneConfig[]>
  selectedZoneIndex: Ref<number>
  dirty: Ref<boolean>
  onResolutionChanged: (prev: SourceResolution, next: SourceResolution) => void
}) {
  const canvasRef = ref<HTMLCanvasElement | null>(null)
  const containerRef = ref<HTMLDivElement | null>(null)
  const canvasWidth = ref<number>(ZONE_GEOMETRY_CONSTANTS.fallbackCanvasWidth)
  const canvasHeight = ref<number>(
    (ZONE_GEOMETRY_CONSTANTS.fallbackCanvasWidth * ZONE_GEOMETRY_CONSTANTS.defaultResolution.height) /
      ZONE_GEOMETRY_CONSTANTS.defaultResolution.width,
  )
  const draggingIndex = ref<number | null>(null)
  const previewState = ref<'live' | 'paused' | 'unavailable'>('unavailable')
  const previewImageSrc = ref('')

  const hasVideoPreview = computed(() => previewState.value !== 'unavailable')

  function resizeCanvas(): void {
    const container = containerRef.value
    if (!container) return
    const nextSize = computeCanvasDimensions(container.clientWidth, params.sourceResolution.value)
    canvasWidth.value = nextSize.width
    canvasHeight.value = nextSize.height

    const canvas = canvasRef.value
    if (!canvas) return
    const ratio = window.devicePixelRatio || 1
    canvas.width = Math.round(canvasWidth.value * ratio)
    canvas.height = Math.round(canvasHeight.value * ratio)
    canvas.style.width = `${canvasWidth.value}px`
    canvas.style.height = `${canvasHeight.value}px`
  }

  function drawCanvas(): void {
    const canvas = canvasRef.value
    const ctx = canvas?.getContext('2d')
    if (!ctx) return

    drawZoneScene({
      ctx,
      canvasWidth: canvasWidth.value,
      canvasHeight: canvasHeight.value,
      dpr: window.devicePixelRatio || 1,
      resolution: params.sourceResolution.value,
      hasVideoPreview: hasVideoPreview.value,
      zones: params.displayZones.value,
      selectedZoneIndex: params.selectedZoneIndex.value,
      activePolygon: params.polygonPoints.value,
    })
  }

  function updatePreviewResolution(image: HTMLImageElement): void {
    const width = image.naturalWidth
    const height = image.naturalHeight
    const previous = params.sourceResolution.value
    if (!width || !height || (width === previous.width && height === previous.height)) return
    params.onResolutionChanged(previous, { width, height })
    nextTick(() => {
      resizeCanvas()
      drawCanvas()
    })
  }

  function resumePreview(): void {
    const cameraId = params.selectedCameraId.value
    if (!cameraId) return
    previewState.value = 'live'
    previewImageSrc.value = `${previewUrl(cameraId)}?t=${Date.now()}`

    // Multipart MJPEG does not reliably fire image onload; probe a single JPEG frame too.
    const frame = new Image()
    frame.onload = () => {
      if (params.selectedCameraId.value === cameraId) {
        updatePreviewResolution(frame)
      }
    }
    frame.src = `${previewFrameUrl(cameraId)}?t=${Date.now()}`
  }

  function pausePreview(): void {
    const cameraId = params.selectedCameraId.value
    if (!cameraId) return
    previewState.value = 'paused'
    previewImageSrc.value = `${previewFrameUrl(cameraId)}?t=${Date.now()}`
  }

  function onPreviewError(): void {
    previewImageSrc.value = ''
    previewState.value = 'unavailable'
  }

  function onPreviewLoad(event: Event): void {
    updatePreviewResolution(event.target as HTMLImageElement)
  }

  function onMouseDown(event: MouseEvent): void {
    const canvas = canvasRef.value
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const mouseX = event.clientX - rect.left
    const mouseY = event.clientY - rect.top
    const scaleX = canvasWidth.value / params.sourceResolution.value.width
    const scaleY = canvasHeight.value / params.sourceResolution.value.height

    const hitIdx = hitTestPolygonVertex(params.polygonPoints.value, mouseX, mouseY, scaleX, scaleY)
    if (hitIdx !== -1) {
      draggingIndex.value = hitIdx
      return
    }
    params.polygonPoints.value.push(
      canvasPointToSource(mouseX, mouseY, scaleX, scaleY, params.sourceResolution.value),
    )
    params.dirty.value = true
    drawCanvas()
  }

  function onMouseMove(event: MouseEvent): void {
    if (draggingIndex.value === null) return
    const canvas = canvasRef.value
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const mouseX = Math.max(0, Math.min(event.clientX - rect.left, canvasWidth.value))
    const mouseY = Math.max(0, Math.min(event.clientY - rect.top, canvasHeight.value))
    const scaleX = canvasWidth.value / params.sourceResolution.value.width
    const scaleY = canvasHeight.value / params.sourceResolution.value.height

    params.polygonPoints.value[draggingIndex.value] = canvasPointToSource(
      mouseX,
      mouseY,
      scaleX,
      scaleY,
      params.sourceResolution.value,
    )
    params.dirty.value = true
    drawCanvas()
  }

  function onMouseUp(): void {
    draggingIndex.value = null
  }

  let resizeObserver: ResizeObserver | undefined

  function observeContainer(): void {
    resizeObserver?.disconnect()
    resizeObserver = new ResizeObserver(() => {
      resizeCanvas()
      drawCanvas()
    })
    if (containerRef.value) {
      resizeObserver.observe(containerRef.value)
    }
  }

  onBeforeUnmount(() => {
    resizeObserver?.disconnect()
  })

  return {
    canvasRef,
    containerRef,
    previewState,
    previewImageSrc,
    resizeCanvas,
    drawCanvas,
    resumePreview,
    pausePreview,
    onPreviewError,
    onPreviewLoad,
    onMouseDown,
    onMouseMove,
    onMouseUp,
    observeContainer,
  }
}
