<template>
  <div class="monitor-dashboard" :class="{ 'focus-mode': focusMode }">
    <header class="page-heading">
      <div>
        <p class="eyebrow">LIVE MONITORING</p>
        <h1>{{ t('dashboard.title') }}</h1>
        <p class="subtitle">{{ t('dashboard.subtitle') }}</p>
      </div>
      <div class="heading-actions">
        <label class="auto-refresh">
          <input v-model="autoRefresh" type="checkbox" />
          {{ t('dashboard.realtimePush') }}
          <span v-if="autoRefresh && streamStateLabel" class="stream-badge" :class="streamState">{{ streamStateLabel }}</span>
        </label>
        <button class="monitor-button" :disabled="loading" @click="refreshAll">
          <el-icon><Refresh /></el-icon>
          {{ loading ? t('dashboard.updating') : t('dashboard.refreshData') }}
        </button>
      </div>
    </header>

    <div v-if="isMockEnabled" class="notice">{{ t('dashboard.mockNotice') }}</div>
    <div v-if="errorLabels.length" class="notice error" role="alert">
      {{ t('dashboard.readFailed', { labels: errorLabels.join('、') }) }}
      {{ hasAnyData ? t('dashboard.keepLastData') : t('dashboard.noSiteData') }}
      <button :disabled="loading" @click="refreshAll">{{ t('dashboard.reload') }}</button>
    </div>

    <nav class="quick-actions" :aria-label="t('dashboard.quickActionsAria')">
      <router-link to="/cameras"><el-icon><VideoCamera /></el-icon>{{ t('dashboard.quickDevice') }}<span>↗</span></router-link>
      <router-link to="/violations"><el-icon><Warning /></el-icon>{{ t('dashboard.quickViolations') }}<span>↗</span></router-link>
      <router-link to="/copilot"><el-icon><ChatDotRound /></el-icon>{{ t('dashboard.quickCopilot') }}<span>↗</span></router-link>
      <router-link to="/learning"><el-icon><CircleCheck /></el-icon>{{ t('dashboard.quickLearning') }}<span>↗</span></router-link>
    </nav>

    <DashboardMetricsRow
      :camera-loaded="cameraLoaded"
      :online-count="onlineCamerasCount"
      :total-cameras="cameras.length"
      :cameras-stale="errors.cameras"
      :camera-source-time="sourceTime('cameras')"
      :stats="stats"
      :day-label="dayLabel"
      :stats-stale="errors.stats"
      :stats-source-time="sourceTime('stats')"
    />

    <div class="workspace-grid">
      <DashboardVideoWall
        v-model:focus-mode="focusMode"
        :cameras="cameras"
        :events="events"
        :camera-loaded="cameraLoaded"
        :cameras-stale="Boolean(errors.cameras)"
        :loading="loading"
        :page-visible="pageVisible"
      />

      <DashboardEventsAside
        :event-loaded="eventLoaded"
        :events="events"
        :event-total="eventTotal"
        :loading="loading"
        :events-source-time="sourceTime('events')"
        :violation-label="violationLabel"
        :severity-label="severityLabel"
        :format-event-time="formatEventTime"
        @open-evidence="openEvidence"
      />
    </div>

    <DashboardAnalyticsSection
      :stats="stats"
      :heatmap="heatmap"
      :violation-labels="typeNames"
      :severity-keys="severityKeys"
      :severity-label="severityLabel"
      :day-label="dayLabel"
      :stats-error="errors.stats"
      :loading="loading"
      :stats-source-time="sourceTime('stats')"
      :chart-animation="chartAnimation"
      @refresh="refreshAll"
    />

    <EvidenceModal v-model="evidenceVisible" :record="selectedEvent" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ChatDotRound, CircleCheck, Refresh, VideoCamera, Warning } from '@element-plus/icons-vue'
import { fetchCameras } from '@/api/cameras'
import { fetchRiskHeatmap, fetchViolations, fetchViolationStatistics, type RiskHeatmapData } from '@/api/violations'
import { useSafetyStream } from '@/composables/useSafetyStream'
import { APP_CONFIG } from '@/config/runtime'
import DashboardAnalyticsSection from '@/components/dashboard/DashboardAnalyticsSection.vue'
import DashboardEventsAside from '@/components/dashboard/DashboardEventsAside.vue'
import DashboardMetricsRow from '@/components/dashboard/DashboardMetricsRow.vue'
import DashboardVideoWall from '@/components/dashboard/DashboardVideoWall.vue'
import EvidenceModal from '@/components/EvidenceModal.vue'
import { useAppI18n, useLocaleRefresh } from '@/i18n/useAppI18n'
import { useDictionariesStore } from '@/stores/dictionaries'
import type { CameraStatusResponse, ViolationRecord, ViolationSeverity, ViolationStatistics, ViolationType } from '@/types/contract'
import { applyRealtimeCameraStatus, applyRealtimeViolationEvent, todayWindow } from '@/utils/monitoring'

const { t, formatDate, formatTime: formatLocaleTime, formatDateTime } = useAppI18n()
const isMockEnabled = APP_CONFIG.useMock
const dictionaries = useDictionariesStore()
dictionaries.ensureLoaded()

const cameras = ref<CameraStatusResponse[]>([])
const stats = ref<ViolationStatistics | null>(null)
const events = ref<ViolationRecord[]>([])
const eventTotal = ref(0)
const heatmap = ref<RiskHeatmapData | null>(null)
const cameraLoaded = ref(false), eventLoaded = ref(false), loading = ref(false), autoRefresh = ref(true), focusMode = ref(false)
const pageVisible = ref(!document.hidden)
const errors = reactive({ cameras: false, stats: false, events: false })
const updatedAt = reactive<Record<'cameras' | 'stats' | 'events', Date | null>>({ cameras: null, stats: null, events: null })
const statsDayRef = ref(new Date())
const dayLabel = computed(() => formatDate(statsDayRef.value, { month: '2-digit', day: '2-digit' }))
const evidenceVisible = ref(false), selectedEvent = ref<ViolationRecord | null>(null)

const errorLabels = computed(() => {
  const sourceLabels = { cameras: t('dashboard.sourceCameras'), stats: t('dashboard.sourceStats'), events: t('dashboard.sourceEvents') }
  return (Object.keys(errors) as (keyof typeof errors)[]).filter((k) => errors[k]).map((k) => sourceLabels[k])
})
const hasAnyData = computed(() => cameraLoaded.value || eventLoaded.value || stats.value !== null)
const onlineCamerasCount = computed(() => cameras.value.filter((c) => c.is_online).length)
const severityKeys: ViolationSeverity[] = ['INFO', 'WARNING', 'CRITICAL']
const chartAnimation = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
const typeNames = computed<Record<ViolationType, string>>(() => dictionaries.violationLabels)
const violationLabel = (type: ViolationType) => dictionaries.violationLabel(type)
const severityLabel = (severity: ViolationSeverity) => dictionaries.severityLabel(severity)
const formatEventTime = (value: string | Date, date = false) =>
  date ? formatDateTime(value, { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : formatLocaleTime(value)

function sourceTime(key: keyof typeof errors) {
  if (!updatedAt[key]) return t('dashboard.noDataYet')
  const formatted = formatEventTime(updatedAt[key]!)
  return errors[key] ? t('dashboard.lastSuccessAt', { time: formatted }) : t('dashboard.updatedAt', { time: formatted })
}

const openEvidence = (event: ViolationRecord) => { selectedEvent.value = event; evidenceVisible.value = true }

let alive = true
let timer: ReturnType<typeof setInterval> | undefined
let statsDebounceTimer: ReturnType<typeof setTimeout> | undefined
let lastFullRefreshAt = 0

const { streamState, start: startSafetyStream, stop: stopEventStream } = useSafetyStream()
const streamStateLabel = computed(() =>
  ({ connected: t('dashboard.streamConnected'), connecting: t('dashboard.streamConnecting'), reconnecting: t('dashboard.streamReconnecting'), closed: '', disabled: '' })[streamState.value],
)

async function refreshStatsAndHeatmap() {
  const now = new Date()
  try {
    const statsResult = await fetchViolationStatistics(todayWindow(now))
    if (!alive) return
    stats.value = statsResult; errors.stats = false; updatedAt.stats = new Date(); statsDayRef.value = now
  } catch { if (alive) errors.stats = true }
  fetchRiskHeatmap(7).then((data) => { if (alive) heatmap.value = data }).catch(() => {})
}

function scheduleStatsRefresh() {
  if (statsDebounceTimer) clearTimeout(statsDebounceTimer)
  statsDebounceTimer = setTimeout(() => { if (alive) void refreshStatsAndHeatmap() }, 300)
}

function startEventStream() {
  if (!autoRefresh.value) return stopEventStream()
  startSafetyStream({
    onCameraStatus(incoming) {
      if (!alive) return
      cameras.value = applyRealtimeCameraStatus(cameras.value, incoming)
      cameraLoaded.value = true; errors.cameras = false; updatedAt.cameras = new Date()
    },
    onViolationEvent(payload) {
      if (!alive) return
      const next = applyRealtimeViolationEvent(events.value, eventTotal.value, payload.record, 6)
      events.value = next.events; eventTotal.value = next.eventTotal
      eventLoaded.value = true; errors.events = false; updatedAt.events = new Date()
      scheduleStatsRefresh()
    },
  })
}

watch(autoRefresh, (enabled) => { if (enabled) { startEventStream(); void refreshAll() } else { stopEventStream() } })

async function refreshAll() {
  if (loading.value) return
  loading.value = true
  const now = new Date()
  try {
    const [cameraResult, statsResult, eventResult] = await Promise.allSettled([
      fetchCameras(), fetchViolationStatistics(todayWindow(now)), fetchViolations({ status: 'ACTIVE', limit: 6, offset: 0 }),
    ])
    fetchRiskHeatmap(7).then((data) => { if (alive) heatmap.value = data }).catch(() => {})
    if (!alive) return
    lastFullRefreshAt = Date.now()
    errors.cameras = cameraResult.status === 'rejected'; errors.stats = statsResult.status === 'rejected'; errors.events = eventResult.status === 'rejected'
    if (cameraResult.status === 'fulfilled') { cameras.value = cameraResult.value; cameraLoaded.value = true; updatedAt.cameras = new Date() }
    if (statsResult.status === 'fulfilled') { stats.value = statsResult.value; updatedAt.stats = new Date(); statsDayRef.value = now }
    if (eventResult.status === 'fulfilled') { events.value = eventResult.value.items.filter((e) => e.status === 'ACTIVE').slice(0, 6); eventTotal.value = eventResult.value.total; eventLoaded.value = true; updatedAt.events = new Date() }
  } finally { if (alive) loading.value = false }
}

const onVisibility = () => { pageVisible.value = !document.hidden; if (pageVisible.value && autoRefresh.value) void refreshAll() }
useLocaleRefresh(() => { if (autoRefresh.value) startEventStream(); void refreshAll() })
onMounted(() => {
  void refreshAll(); startEventStream()
  timer = setInterval(() => {
    if (!autoRefresh.value || document.hidden) return
    if (Date.now() - lastFullRefreshAt >= (streamState.value === 'connected' ? 60000 : 30000)) void refreshAll()
  }, 15000)
  document.addEventListener('visibilitychange', onVisibility)
})
onUnmounted(() => { alive = false; clearInterval(timer); if (statsDebounceTimer) clearTimeout(statsDebounceTimer); document.removeEventListener('visibilitychange', onVisibility) })
</script>

<style scoped>
.monitor-dashboard { --line: #ece9f3; max-width: 1512px; margin: 0 auto; padding: 32px 32px 40px; color: #545d70; }
.page-heading { display: flex; justify-content: space-between; align-items: center; gap: 20px; margin-bottom: 26px; }
.eyebrow { display: flex; align-items: center; gap: 9px; font-size: 10px; font-weight: 600; letter-spacing: 1.8px; color: #9584c7; margin: 0 0 10px; }
.page-heading h1 { font-size: 27px; font-weight: 650; line-height: 1.4; letter-spacing: -.5px; color: #343b51; margin: 0; }
.page-heading .subtitle { font-size: 13px; line-height: 1.8; color: #737b8d; margin: 11px 0 0; }
.heading-actions { display: flex; align-items: center; gap: 18px; }
.auto-refresh { font-size: 11px; color: #737b8d; white-space: nowrap; }
.auto-refresh input { accent-color: #8879df; vertical-align: middle; margin-right: 6px; }
.monitor-button { border: 0; border-radius: 11px; background: #fff; color: #8370b6; display: inline-flex; align-items: center; gap: 8px; padding: 12px 18px; font-size: 12px; min-height: 37px; white-space: nowrap; }
.monitor-button:disabled { opacity: .5; }
.notice { padding: 10px 14px; border: 1px solid #e8e2f3; background: #f1eefb; color: #82759e; font-size: 11px; border-radius: 12px; margin-bottom: 18px; line-height: 1.7; }
.notice.error { background: #fff0ec; color: #bd7a67; border-color: #f2dcd5; }
.notice button { color: inherit; background: none; border: 0; text-decoration: underline; margin-left: 15px; }
.quick-actions { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 0 0 24px; }
.quick-actions a { display: flex; align-items: center; gap: 9px; min-height: 40px; background: #fff; border: 1px solid #eae5f4; border-radius: 12px; padding: 14px 16px; color: #84739e; font-size: 12px; text-decoration: none; transition: box-shadow .2s, transform .2s, background .2s; }
.quick-actions a:hover { background: #f3eefb; border-color: #cfc0e9; transform: translateY(-2px); box-shadow: 0 4px 12px #615a9910; }
.quick-actions a > span { margin-left: auto; color: #a09aaa; }
.workspace-grid { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 22px; align-items: start; }
.focus-mode .workspace-grid { grid-template-columns: 1fr; }
.focus-mode :deep(.event-column) { display: none; }
.stream-badge { display: inline-flex; align-items: center; gap: 4px; margin-left: 6px; padding: 2px 7px; border-radius: 10px; font-size: 10px; font-weight: 500; background: #eef6f0; color: #4e9a67; }
.stream-badge::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.stream-badge.connecting, .stream-badge.reconnecting { background: #fef6e7; color: #b88230; }

@media (min-width: 1650px) { .monitor-dashboard { padding: 36px 40px 44px; } .workspace-grid { grid-template-columns: minmax(0, 1fr) 310px; gap: 24px; } }
@media (max-width: 1250px) { .monitor-dashboard { padding: 28px 24px; } .workspace-grid { grid-template-columns: minmax(0, 1fr) 270px; gap: 18px; } }
@media (max-width: 1100px) { .workspace-grid { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 760px) {
  .monitor-dashboard { padding: 24px 16px; }
  .page-heading { align-items: start; flex-direction: column; gap: 18px; }
  .page-heading h1 { font-size: 24px; }
  .page-heading .subtitle { font-size: 12px; }
  .heading-actions { width: 100%; justify-content: space-between; flex-direction: row; align-items: center; }
  .auto-refresh { font-size: 10px; }
  .quick-actions { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; }
  .quick-actions a { padding: 12px; font-size: 11px; }
}
</style>
