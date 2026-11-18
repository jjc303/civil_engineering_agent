<template>
  <section ref="videoPanel" tabindex="-1" class="video-panel" :class="{ 'focus-layout': focusMode }" :aria-label="t('dashboard.videoWallAria')">
    <div class="section-heading">
      <div>
        <h2>{{ t('dashboard.videoSectionTitle') }}</h2>
        <p>{{ t('dashboard.videoSectionDesc') }}</p>
      </div>
      <div class="view-controls">
        <button class="focus-toggle" :aria-pressed="focusMode" @click="$emit('update:focusMode', !focusMode)">
          {{ focusMode ? t('dashboard.exitFocus') : t('dashboard.enterFocus') }}
        </button>
        <div class="layout-switch" role="group" :aria-label="t('dashboard.layoutAria')">
          <button v-for="n in [1, 4, 6]" :key="n" :aria-pressed="layout === n" @click="setLayout(n)">
            {{ n === 1 ? t('dashboard.layout1') : n === 4 ? t('dashboard.layout4') : t('dashboard.layout6') }}
          </button>
        </div>
        <button
          class="icon-button"
          :aria-label="fullscreen ? t('dashboard.exitFullscreenAria') : t('dashboard.enterFullscreenAria')"
          @click="toggleFullscreen"
        >
          <el-icon><FullScreen /></el-icon>
        </button>
      </div>
    </div>

    <div class="camera-filters">
      <label class="camera-search">
        <el-icon><Search /></el-icon>
        <input v-model="cameraQuery" type="search" :placeholder="t('dashboard.searchCameraPlaceholder')" :aria-label="t('dashboard.searchCameraAria')" />
      </label>
      <div class="status-filter" role="group" :aria-label="t('dashboard.statusFilterAria')">
        <button v-for="option in statusOptions" :key="option.value" :aria-pressed="cameraStatus === option.value" @click="cameraStatus = option.value">
          {{ option.label }}
        </button>
      </div>
    </div>

    <div class="camera-toolbar">
      <label v-if="layout === 1">
        {{ t('dashboard.currentChannel') }}
        <select v-model="selectedCameraId" :aria-label="t('dashboard.selectChannelAria')" :disabled="!filteredCameras.length">
          <option v-for="camera in filteredCameras" :key="camera.camera_id" :value="camera.camera_id">{{ camera.camera_id }}</option>
        </select>
      </label>
      <span v-else>{{ t('dashboard.channelSummary', { matched: cameraLoaded ? filteredCameras.length : '—', total: cameras.length }) }}</span>
      <button v-if="cameraQuery || cameraStatus !== 'all'" class="clear-filter" @click="clearFilters">{{ t('dashboard.clearFilter') }}</button>
    </div>

    <div v-if="!cameraLoaded" class="section-empty">
      <el-icon><VideoCamera /></el-icon>
      <h3>{{ loading ? t('dashboard.fetchingCameras') : t('dashboard.camerasUnavailable') }}</h3>
      <p>{{ t('dashboard.camerasConnectHint') }}</p>
    </div>
    <div v-else-if="!cameras.length" class="section-empty">
      <el-icon><VideoCamera /></el-icon>
      <h3>{{ t('dashboard.noCamerasTitle') }}</h3>
      <p>{{ t('dashboard.noCamerasDesc') }}</p>
      <router-link to="/cameras">{{ t('dashboard.goDeviceMgmt') }}</router-link>
    </div>
    <div v-else-if="!filteredCameras.length" class="section-empty">
      <el-icon><Search /></el-icon>
      <h3>{{ t('dashboard.noMatchedCameras') }}</h3>
      <p>{{ t('dashboard.noMatchedCamerasDesc') }}</p>
      <button class="monitor-button" @click="clearFilters">{{ t('dashboard.clearFilter') }}</button>
    </div>
    <div v-else class="video-grid" :class="`grid-${layout}`">
      <MonitorCamera
        v-for="camera in displayedCameras"
        :key="camera.camera_id"
        :camera="camera"
        :index="cameras.findIndex(c => c.camera_id === camera.camera_id)"
        :active-event-count="events.filter(e => e.camera_id === camera.camera_id).length"
        :stale="camerasStale"
        :preview-allowed="pageVisible"
        @focus="focusCamera"
      />
    </div>
    <div v-if="layout > 1 && filteredCameras.length" class="page-controls">
      <span>{{ t('dashboard.pageControls', { page: cameraPageNumber, total: pageCount, count: filteredCameras.length }) }}</span>
      <div>
        <button class="icon-button" :aria-label="t('dashboard.prevPageAria')" :disabled="cameraPageNumber <= 1" @click="cameraPageNumber--">←</button>
        <button class="icon-button" :aria-label="t('dashboard.nextPageAria')" :disabled="cameraPageNumber >= pageCount" @click="cameraPageNumber++">→</button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { FullScreen, Search, VideoCamera } from '@element-plus/icons-vue'
import MonitorCamera from '@/components/MonitorCamera.vue'
import { useAppI18n } from '@/i18n/useAppI18n'
import type { CameraStatusResponse, ViolationRecord } from '@/types/contract'
import { cameraPage, cameraSelection, filterCameras } from '@/utils/monitoring'

const props = defineProps<{
  cameras: CameraStatusResponse[]
  events: ViolationRecord[]
  cameraLoaded: boolean
  camerasStale: boolean
  loading: boolean
  pageVisible: boolean
  focusMode: boolean
}>()

defineEmits<{
  'update:focusMode': [val: boolean]
}>()

const { t } = useAppI18n()
const cameraQuery = ref('')
const cameraStatus = ref<'all' | 'online' | 'offline'>('all')
const selectedCameraId = ref('')
const cameraPageNumber = ref(1)
const layout = ref(4)
const videoPanel = ref<HTMLElement | null>(null)
const fullscreen = ref(false)

const statusOptions = computed(() => [
  { value: 'all', label: t('dashboard.statusAll') },
  { value: 'online', label: t('dashboard.statusOnline') },
  { value: 'offline', label: t('dashboard.statusOffline') },
] as const)

const filteredCameras = computed(() => filterCameras(props.cameras, cameraQuery.value, cameraStatus.value))
const pageCount = computed(() => Math.max(1, Math.ceil(filteredCameras.value.length / layout.value)))
const displayedCameras = computed(() => cameraPage(filteredCameras.value, layout.value, cameraPageNumber.value, selectedCameraId.value))

watch([cameraQuery, cameraStatus], () => { cameraPageNumber.value = 1 })
watch(
  filteredCameras,
  (value) => {
    selectedCameraId.value = cameraSelection(value, selectedCameraId.value)
    cameraPageNumber.value = Math.min(cameraPageNumber.value, pageCount.value)
  },
  { immediate: true },
)

const clearFilters = () => { cameraQuery.value = ''; cameraStatus.value = 'all' }
const setLayout = (count: number) => { layout.value = count; cameraPageNumber.value = 1 }
const focusCamera = (id: string) => { selectedCameraId.value = id; layout.value = 1 }

async function toggleFullscreen() {
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await videoPanel.value?.requestFullscreen()
  } catch {
    ElMessage.info(t('dashboard.fullscreenUnsupported'))
  }
}

const syncFullscreen = () => { fullscreen.value = document.fullscreenElement === videoPanel.value }
onMounted(() => document.addEventListener('fullscreenchange', syncFullscreen))
onUnmounted(() => document.removeEventListener('fullscreenchange', syncFullscreen))
</script>

<style scoped>
.video-panel { padding: 22px; border: 1px solid #ece9f4; border-radius: 20px; background: #fff; min-width: 0; scroll-margin-top: 20px; }
.video-panel:fullscreen { padding: 28px; background: #f7f8fc; overflow: auto; border-radius: 0; }
.video-panel:fullscreen .grid-1 { max-width: 1100px; margin: auto; }
.section-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 16px; }
.section-heading h2 { font-size: 15px; font-weight: 600; margin: 0; color: #4a526b; }
.section-heading p { font-size: 11px; color: #737b8d; line-height: 1.7; margin: 7px 0 0; }
.view-controls { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.layout-switch { display: flex; padding: 4px; background: #f2f1f8; border: 0; border-radius: 10px; }
.layout-switch button { background: none; color: #9195a5; border: 0; padding: 7px 12px; min-height: 32px; font-size: 11px; border-radius: 18px; transition: background .2s, box-shadow .2s, color .2s; }
.layout-switch button[aria-pressed=true] { background: #fff; box-shadow: 0 2px 7px #43386c15; color: #7969cd; }
.icon-button { display: inline-grid; place-items: center; border: 0; border-radius: 50%; width: 36px; height: 36px; background: #f3f2fa; color: #8b80ba; font-size: 13px; }
.icon-button:disabled { opacity: .3; }
.camera-filters { display: flex; gap: 12px; justify-content: space-between; align-items: center; margin: 18px 0 12px; flex-wrap: wrap; }
.camera-search { display: flex; align-items: center; gap: 8px; padding: 9px 12px; border: 1px solid #eeebf6; border-radius: 14px; background: #f9f8fd; color: #aaa0c0; flex: 1; min-width: 150px; max-width: 300px; transition: box-shadow .2s, border-color .2s; }
.camera-search:focus-within { border-color: #b4a6e2; box-shadow: 0 0 0 3px #eee8fb; }
.camera-search input { width: 100%; min-width: 0; background: transparent; border: 0; outline: none; font-size: 12px; color: #747087; }
.camera-search input::placeholder { color: #aaa4b6; }
.status-filter { display: flex; gap: 4px; border-radius: 10px; }
.status-filter button, .focus-toggle, .clear-filter { background: transparent; border: 0; border-radius: 18px; color: #9386ac; padding: 9px 12px; font-size: 11px; min-height: 36px; }
.status-filter button:hover, .clear-filter:hover { background: #f6f2fc; }
.status-filter button[aria-pressed=true], .focus-toggle[aria-pressed=true] { background: #eee8fa; color: #7c68b2; }
.focus-toggle { border: 1px solid #e9e3f5; white-space: nowrap; }
.clear-filter { padding: 4px 9px; min-height: auto; }
.camera-toolbar { display: flex; justify-content: space-between; align-items: center; font-size: 10px; color: #737b8d; margin-bottom: 16px; min-height: 27px; }
.camera-toolbar select { margin-left: 10px; max-width: 230px; padding: 7px 10px; border-radius: 12px; background: #f5f3fc; color: #7b7198; border: 1px solid #e9e4f6; font-size: 11px; }
.video-grid { display: grid; gap: 14px; transition: gap .2s; }
.grid-1 { grid-template-columns: 1fr; }
.grid-4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.grid-6 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.focus-layout .grid-4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.focus-layout .grid-6 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.section-empty { min-height: 310px; border: 1px dashed #e4e5ef; border-radius: 16px; padding: 45px 22px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; color: #a09ab9; }
.section-empty > .el-icon { font-size: 28px; }
.section-empty h3 { font-size: 14px; font-weight: 400; color: #74798c; margin: 18px 0 8px; }
.section-empty p { font-size: 12px; margin: 0; line-height: 1.9; color: #858c9d; }
.section-empty a { font-size: 12px; color: #7969d0; margin-top: 20px; }
.monitor-button { margin-top: 16px; border: 0; border-radius: 11px; background: #ece8fc; color: #7565c9; padding: 12px 18px; font-size: 12px; }
.page-controls { display: flex; justify-content: space-between; align-items: center; margin-top: 18px; font-size: 10px; color: #81889a; }
.page-controls > div { display: flex; gap: 6px; }
.page-controls:has(button:disabled + button:disabled) { opacity: .6; }

@media (max-width: 1250px) { .video-panel { padding: 18px; } .grid-6 { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) {
  .video-panel { padding: 16px; border-radius: 16px; }
  .grid-4, .grid-6, .focus-layout .grid-4, .focus-layout .grid-6 { grid-template-columns: 1fr; }
  .camera-search { max-width: none; }
  .status-filter { width: 100%; justify-content: flex-start; }
  .view-controls { width: 100%; justify-content: space-between; gap: 7px; }
  .focus-toggle { padding: 7px 10px; }
  .camera-toolbar select { max-width: 155px; }
}
</style>
