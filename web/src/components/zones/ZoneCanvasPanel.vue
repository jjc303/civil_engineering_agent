<template>
  <el-card shadow="never" class="canvas-card">
    <template #header>
      <div class="canvas-toolbar">
        <div class="canvas-title">
          <strong>{{ t('zones.canvasTitle') }}</strong>
          <small>{{ t('zones.canvasResolution', { width: resolution.width, height: resolution.height }) }}</small>
        </div>
        <div class="tool-btns">
          <el-tag size="small" :type="previewState === 'live' ? 'success' : previewState === 'paused' ? 'warning' : 'info'">
            {{ previewLabel }}
          </el-tag>
          <el-button size="small" :disabled="!cameraId" @click="pausePreview">
            {{ previewState === 'paused' ? t('zones.refreshFrame') : t('zones.pausePreview') }}
          </el-button>
          <el-button size="small" :disabled="!cameraId || previewState === 'live'" @click="resumePreview">
            {{ t('zones.resumePreview') }}
          </el-button>
          <el-button size="small" type="primary" :icon="Plus" @click="$emit('addPoint')">{{ t('zones.addPoint') }}</el-button>
          <el-button size="small" :icon="RefreshRight" @click="$emit('resetDefault')">{{ t('zones.resetDefault') }}</el-button>
          <el-button size="small" type="danger" :icon="Delete" @click="$emit('clearPoints')">{{ t('zones.clearPoints') }}</el-button>
        </div>
      </div>
    </template>

    <div ref="containerRef" class="canvas-container">
      <img
        v-if="previewImageSrc"
        class="preview-background"
        :src="previewImageSrc"
        :alt="t('zones.previewAlt')"
        @load="onPreviewLoad"
        @error="onPreviewError"
      />
      <canvas
        ref="canvasRef"
        class="interactive-canvas"
        @mousedown="onMouseDown"
        @mousemove="onMouseMove"
        @mouseup="onMouseUp"
      />
    </div>

    <div class="canvas-hint">
      <span>
        {{ t('zones.canvasHintPrefix') }}
        <strong>{{ t('zones.canvasHintPoint') }}</strong>
        {{ t('zones.canvasHintMiddle') }}
        {{ previewState === 'unavailable' ? t('zones.canvasHintUnavailable') : t('zones.canvasHintAvailable') }}
      </span>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, toRef, watch } from 'vue'
import { Delete, Plus, RefreshRight } from '@element-plus/icons-vue'
import { useZoneCanvas } from '@/composables/useZoneCanvas'
import { useAppI18n } from '@/i18n/useAppI18n'
import type { DangerZoneConfig, SourceResolution } from '@/types/contract'
import type { Point2D } from '@/utils/zoneGeometry'

const props = defineProps<{
  cameraId: string
  resolution: SourceResolution
  zones: DangerZoneConfig[]
  selectedZoneIndex: number
  polygonPoints: Point2D[]
  dirty: boolean
}>()

const emit = defineEmits<{
  'update:dirty': [val: boolean]
  addPoint: []
  resetDefault: []
  clearPoints: []
  resolutionChange: [prev: SourceResolution, next: SourceResolution]
}>()

const { t } = useAppI18n()

const dirtyProxy = computed({
  get: () => props.dirty,
  set: (val) => emit('update:dirty', val),
})

const {
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
} = useZoneCanvas({
  selectedCameraId: toRef(props, 'cameraId'),
  sourceResolution: toRef(props, 'resolution'),
  polygonPoints: toRef(props, 'polygonPoints'),
  displayZones: toRef(props, 'zones'),
  selectedZoneIndex: toRef(props, 'selectedZoneIndex'),
  dirty: dirtyProxy,
  onResolutionChanged: (prev, next) => emit('resolutionChange', prev, next),
})

const previewLabel = computed(() =>
  ({
    live: t('zones.previewLive'),
    paused: t('zones.previewPaused'),
    unavailable: t('zones.previewUnavailable'),
  })[previewState.value],
)

watch(
  () => [props.polygonPoints, props.zones, props.selectedZoneIndex],
  () => drawCanvas(),
  { deep: true },
)

onMounted(() => {
  observeContainer()
  nextTick(() => {
    resizeCanvas()
    drawCanvas()
  })
})

function resizeAndDraw(): void {
  nextTick(() => {
    resizeCanvas()
    drawCanvas()
  })
}

defineExpose({
  resumePreview,
  resizeAndDraw,
  drawCanvas,
})
</script>

<style scoped>
.canvas-card { min-width: 0; border-radius: 20px; }
.canvas-toolbar { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.canvas-title strong { display: block; font-size: 14px; font-weight: 600; color: #4b546e; }
.canvas-title small { display: block; font-size: 10px; color: #989cad; margin-top: 7px; }
.tool-btns { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.tool-btns .el-button { margin-left: 0; }
.canvas-container { width: 100%; position: relative; background: #0f172a; border-radius: 12px; overflow: hidden; display: flex; justify-content: center; }
.interactive-canvas { cursor: crosshair; display: block; position: relative; z-index: 1; }
.preview-background { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: fill; z-index: 0; }
.canvas-hint { margin-top: 10px; padding: 13px 15px; background: #f7f4fc; border: 1px solid #eee7f6; border-radius: 10px; line-height: 1.8; color: #9489a4; font-size: 11px; }

@media (max-width: 650px) {
  .canvas-card { border-radius: 16px; }
  .canvas-hint { font-size: 10px; }
  .tool-btns { gap: 6px; }
  .tool-btns .el-button { padding: 7px 9px; }
}
</style>
