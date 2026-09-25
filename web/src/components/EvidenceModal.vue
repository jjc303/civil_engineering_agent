<template>
  <el-dialog
    v-model="visible"
    :title="`违规证据审查 - ${record?.camera_id || ''}`"
    width="860px"
    destroy-on-close
    class="evidence-dialog"
  >
    <div v-if="record" class="evidence-container">
      <div class="meta-bar">
        <el-tag :type="severityTagType(record.severity)" effect="dark" size="small">
          {{ record.severity }}
        </el-tag>
        <span class="type-name">{{ formatViolationType(record.violation_type) }}</span>
        <span class="time-str">时间：{{ formatUtc(record.occurred_at_utc) }}</span>
        <span class="duration-str">持续：{{ record.duration_seconds.toFixed(1) }}s</span>
      </div>

      <div class="image-wrapper" ref="imageWrapperRef">
        <img
          ref="imgRef"
          :src="mediaUrl"
          alt="违规抓拍"
          class="evidence-img"
          @load="onImageLoaded"
          @error="onImageError"
        />
        <canvas ref="canvasRef" class="overlay-canvas"></canvas>
        <div v-if="imgFailed" class="fallback-placeholder">
          <el-icon :size="48"><PictureFilled /></el-icon>
          <p>快照媒体加载失败或不存在 ({{ record.snapshot_uri }})</p>
        </div>
      </div>

      <div class="details-panel">
        <div class="detail-item"><strong>事件 UUID：</strong><code>{{ record.event_uuid }}</code></div>
        <div class="detail-item"><strong>监控会话：</strong>{{ record.monitor_session_id }}</div>
        <div class="detail-item" v-if="record.zone_name"><strong>关联危险区：</strong>{{ record.zone_name }}</div>
        <div class="detail-item" v-if="record.extra_details?.bbox">
          <strong>目标检测框 (原分辨率)：</strong>
          <code>[{{ record.extra_details.bbox.join(', ') }}]</code>
        </div>
        <div class="detail-item" v-if="record.extra_details?.feet_point">
          <strong>脚底判定点：</strong>
          <code>[{{ record.extra_details.feet_point.join(', ') }}]</code>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import type { ViolationRecord, ViolationSeverity, ViolationType } from '@/types/contract'
import { resolveMediaUrl } from '@/api/client'
import { PictureFilled } from '@element-plus/icons-vue'

const props = defineProps<{
  modelValue: boolean
  record: ViolationRecord | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const imgRef = ref<HTMLImageElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const imageWrapperRef = ref<HTMLDivElement | null>(null)
const imgFailed = ref(false)

const mediaUrl = computed(() => {
  if (!props.record?.snapshot_uri) return ''
  return resolveMediaUrl(props.record.snapshot_uri)
})

watch(
  () => props.record,
  () => {
    imgFailed.value = false
    nextTick(() => {
      drawAnnotations()
    })
  }
)

function onImageLoaded() {
  imgFailed.value = false
  drawAnnotations()
}

function onImageError() {
  imgFailed.value = true
}

function drawAnnotations() {
  const img = imgRef.value
  const canvas = canvasRef.value
  const record = props.record
  if (!img || !canvas || !record) return

  const displayWidth = img.clientWidth || 800
  const displayHeight = img.clientHeight || 450

  canvas.width = displayWidth
  canvas.height = displayHeight

  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // 原始物理分辨率假定 1920x1080，如果图片有真实尺寸则采用 natural 尺寸
  const sourceWidth = img.naturalWidth || 1920
  const sourceHeight = img.naturalHeight || 1080

  const scaleX = displayWidth / sourceWidth
  const scaleY = displayHeight / sourceHeight

  const extra = record.extra_details || {}

  // 1. 绘制目标框 bbox
  if (extra.bbox && extra.bbox.length === 4) {
    const [x1, y1, x2, y2] = extra.bbox
    const dx = x1 * scaleX
    const dy = y1 * scaleY
    const dw = (x2 - x1) * scaleX
    const dh = (y2 - y1) * scaleY

    ctx.strokeStyle = '#ef4444'
    ctx.lineWidth = 3
    ctx.strokeRect(dx, dy, dw, dh)

    ctx.fillStyle = 'rgba(239, 68, 68, 0.2)'
    ctx.fillRect(dx, dy, dw, dh)

    // 标签背景
    ctx.fillStyle = '#ef4444'
    ctx.font = 'bold 12px sans-serif'
    const label = `${record.violation_type} #${record.track_id}`
    const textWidth = ctx.measureText(label).width
    ctx.fillRect(dx, dy - 20 > 0 ? dy - 20 : 0, textWidth + 8, 20)
    ctx.fillStyle = '#ffffff'
    ctx.fillText(label, dx + 4, dy - 20 > 0 ? dy - 5 : 15)
  }

  // 2. 绘制脚底接地点 feet_point
  if (extra.feet_point && extra.feet_point.length === 2) {
    const [fx, fy] = extra.feet_point
    const cx = fx * scaleX
    const cy = fy * scaleY

    ctx.beginPath()
    ctx.arc(cx, cy, 6, 0, 2 * Math.PI)
    ctx.fillStyle = '#eab308'
    ctx.fill()
    ctx.lineWidth = 2
    ctx.strokeStyle = '#ffffff'
    ctx.stroke()
  }
}

function severityTagType(s: ViolationSeverity): 'danger' | 'warning' | 'info' {
  if (s === 'CRITICAL') return 'danger'
  if (s === 'WARNING') return 'warning'
  return 'info'
}

function formatViolationType(t: ViolationType): string {
  const map: Record<ViolationType, string> = {
    NO_HELMET: '未佩戴安全帽',
    DANGER_ZONE_INTRUSION: '危险区域入侵',
    DWELL_TIMEOUT: '危险区域停留超时',
  }
  return map[t] || t
}

function formatUtc(utcStr: string): string {
  if (!utcStr) return '-'
  const d = new Date(utcStr)
  return d.toLocaleString()
}
</script>

<style scoped>
.evidence-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.meta-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}
.type-name {
  font-weight: 600;
  color: #1e293b;
}
.time-str, .duration-str {
  color: #64748b;
}
.image-wrapper {
  position: relative;
  width: 100%;
  min-height: 420px;
  background-color: #0f172a;
  border-radius: 6px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.evidence-img {
  width: 100%;
  height: auto;
  max-height: 520px;
  object-fit: contain;
  display: block;
}
.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.fallback-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  padding: 40px;
}
.details-panel {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  background-color: #f1f5f9;
  padding: 12px;
  border-radius: 6px;
  font-size: 13px;
}
.detail-item code {
  background-color: #e2e8f0;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}
</style>
