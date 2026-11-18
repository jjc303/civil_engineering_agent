<template>
  <div class="zone-editor-page operations-workbench">
    <WorkspaceIntro eyebrow="SAFETY ZONES" :title="t('zones.title')" :description="t('zones.description')">
      <div class="camera-picker">
        <span class="label">{{ t('zones.cameraLabel') }}</span>
        <el-select v-model="selectedCameraId" style="width: 200px" @change="handleCameraChange">
          <el-option v-for="cam in cameras" :key="cam.camera_id" :label="cam.camera_id" :value="cam.camera_id" />
        </el-select>
        <el-tag :type="currentVersion > 0 ? 'success' : 'info'" effect="light">
          {{ currentVersion > 0 ? t('zones.configVersion', { version: currentVersion }) : t('zones.notCalibrated') }}
        </el-tag>
      </div>
    </WorkspaceIntro>

    <ZoneWorkflowSteps :camera-id="selectedCameraId" :point-count="polygonPoints.length" :version="currentVersion" :dirty="dirty" />

    <div class="workspace-grid">
      <ZoneCanvasPanel
        ref="canvasPanelRef"
        :camera-id="selectedCameraId"
        :resolution="sourceResolution"
        :zones="displayZones"
        :selected-zone-index="selectedZoneIndex"
        :polygon-points="polygonPoints"
        v-model:dirty="dirty"
        @add-point="addPoint"
        @reset-default="resetToDefaultZone"
        @clear-points="clearPoints"
        @resolution-change="onResolutionChange"
      />

      <ZoneConfigPanel
        :zones="displayZones"
        :selected-zone-index="selectedZoneIndex"
        :zone-config="zoneConfig"
        :rules="form"
        :polygon-points="polygonPoints"
        :save-error="saveError"
        :saving="saving"
        :can-save="Boolean(selectedCameraId && loadedCameraId === selectedCameraId)"
        @select-zone="selectZone"
        @create-zone="createZone"
        @duplicate-zone="duplicateZone"
        @delete-zone="deleteSelectedZone"
        @remove-point="removePoint"
        @save="saveConfiguration"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchCameras } from '@/api/cameras'
import { fetchCameraZones, updateCameraZones } from '@/api/zones'
import ZoneCanvasPanel from '@/components/zones/ZoneCanvasPanel.vue'
import ZoneConfigPanel from '@/components/zones/ZoneConfigPanel.vue'
import ZoneWorkflowSteps from '@/components/zones/ZoneWorkflowSteps.vue'
import WorkspaceIntro from '@/components/WorkspaceIntro.vue'
import { useZoneDraft, type ZoneDraftRules } from '@/composables/useZoneDraft'
import { useAppI18n } from '@/i18n/useAppI18n'
import type { CameraStatusResponse, DangerZoneConfig, SourceResolution } from '@/types/contract'
import {
  ZONE_GEOMETRY_CONSTANTS,
  computeNextPolygonPoint,
  createDefaultPolygon,
  createDefaultZone,
  scalePolygonToResolution,
  type Point2D,
} from '@/utils/zoneGeometry'

const { t } = useAppI18n()
const route = useRoute()
const { saveDraft, loadDraft, clearDraft } = useZoneDraft()

const canvasPanelRef = ref<InstanceType<typeof ZoneCanvasPanel> | null>(null)
const cameras = ref<CameraStatusResponse[]>([])
const selectedCameraId = ref('')
const currentVersion = ref(0)
const saving = ref(false)
const saveError = ref('')
const loadedCameraId = ref('')
const dirty = ref(false)
const hydrating = ref(false)
const zones = ref<DangerZoneConfig[]>([])
const selectedZoneIndex = ref(0)
const sourceResolution = ref<SourceResolution>({ ...ZONE_GEOMETRY_CONSTANTS.defaultResolution })
const polygonPoints = ref<Point2D[]>(createDefaultPolygon())

const zoneConfig = reactive<DangerZoneConfig>({
  zone_id: 'zone-crane-01',
  zone_name: t('zones.defaultInitialZoneName'),
  polygon: [],
  enabled: true,
  alarm_dwell_threshold_seconds: ZONE_GEOMETRY_CONSTANTS.defaultDwellSeconds,
})

const form = reactive<ZoneDraftRules>({ ...ZONE_GEOMETRY_CONSTANTS.defaultDebounceFrames })
const displayZones = computed(() =>
  zones.value.map((zone, index) => (index === selectedZoneIndex.value ? { ...zoneConfig, polygon: polygonPoints.value } : zone)),
)

const buildDefaultZone = (index = 1) => createDefaultZone(index, t('zones.defaultZoneName', { index }), sourceResolution.value)

function syncSelectedZone() {
  if (!zones.value[selectedZoneIndex.value]) return
  zones.value[selectedZoneIndex.value] = { ...zoneConfig, polygon: polygonPoints.value.map(([x, y]) => [x, y] as Point2D) }
}

function hydrateSelectedZone(index = selectedZoneIndex.value) {
  const zone = zones.value[index] || buildDefaultZone(index + 1)
  hydrating.value = true
  Object.assign(zoneConfig, { ...zone, polygon: [] })
  polygonPoints.value = zone.polygon.map(([x, y]) => [x, y] as Point2D)
  nextTick(() => { hydrating.value = false; canvasPanelRef.value?.drawCanvas() })
}

async function init() {
  try {
    const list = await fetchCameras()
    cameras.value = list
    const queryCam = route.query.camera_id as string
    selectedCameraId.value = queryCam && list.some((c) => c.camera_id === queryCam) ? queryCam : list[0]?.camera_id || ''
    if (selectedCameraId.value) await loadCameraConfig()
    else ElMessage.info(t('zones.noCamerasInfo'))
  } catch {
    cameras.value = []
    ElMessage.error(t('zones.fetchCamerasFailed'))
  }
}

async function handleCameraChange(nextCameraId: string) {
  if (dirty.value && loadedCameraId.value && nextCameraId !== loadedCameraId.value) {
    try { await ElMessageBox.confirm(t('zones.unsavedSwitchConfirm'), t('zones.unsavedSwitchTitle'), { type: 'warning' }) }
    catch { selectedCameraId.value = loadedCameraId.value; return }
  }
  await loadCameraConfig()
}

async function loadCameraConfig() {
  if (!selectedCameraId.value) return
  loadedCameraId.value = ''
  try {
    const res = await fetchCameraZones(selectedCameraId.value)
    if (res) {
      currentVersion.value = res.config_version
      sourceResolution.value = { ...res.source_resolution }
      form.enter_debounce_frames = res.enter_debounce_frames
      form.exit_debounce_frames = res.exit_debounce_frames
      form.helmet_debounce_frames = res.helmet_debounce_frames
      zones.value = res.zones.length ? JSON.parse(JSON.stringify(res.zones)) : [buildDefaultZone()]
    } else {
      currentVersion.value = 0
      sourceResolution.value = { ...ZONE_GEOMETRY_CONSTANTS.defaultResolution }
      zones.value = [buildDefaultZone()]
    }
    selectedZoneIndex.value = 0
    hydrateSelectedZone()
    loadedCameraId.value = selectedCameraId.value
    dirty.value = false; saveError.value = ''
    const draft = loadDraft(selectedCameraId.value, currentVersion.value)
    if (draft) {
      zones.value = draft.zones
      selectedZoneIndex.value = Math.min(draft.index || 0, zones.value.length - 1)
      sourceResolution.value = draft.resolution
      Object.assign(form, draft.rules)
      hydrateSelectedZone()
      dirty.value = true
      ElMessage.info(t('zones.draftRestored'))
    }
    canvasPanelRef.value?.resumePreview()
  } catch {
    ElMessage.error(t('zones.loadConfigFailed'))
    return
  }
  canvasPanelRef.value?.resizeAndDraw()
}

const resetToDefaultZone = () => { polygonPoints.value = createDefaultPolygon(sourceResolution.value); dirty.value = true }
const clearPoints = () => { polygonPoints.value = []; dirty.value = true }
const addPoint = () => { polygonPoints.value.push(computeNextPolygonPoint(polygonPoints.value, sourceResolution.value)); dirty.value = true }
function removePoint(idx: number) {
  if (polygonPoints.value.length <= ZONE_GEOMETRY_CONSTANTS.minPolygonPoints) return ElMessage.warning(t('zones.minPointsWarning'))
  polygonPoints.value.splice(idx, 1); dirty.value = true
}
function selectZone(index: number) { if (index !== selectedZoneIndex.value) { syncSelectedZone(); selectedZoneIndex.value = index; hydrateSelectedZone(index) } }
function createZone() { syncSelectedZone(); zones.value.push(buildDefaultZone(zones.value.length + 1)); selectedZoneIndex.value = zones.value.length - 1; hydrateSelectedZone(); dirty.value = true }
function duplicateZone() {
  syncSelectedZone()
  const src = zones.value[selectedZoneIndex.value]!
  const copy = JSON.parse(JSON.stringify(src)) as DangerZoneConfig
  copy.zone_id = `${src.zone_id}-copy-${zones.value.length + 1}`.slice(0, ZONE_GEOMETRY_CONSTANTS.maxZoneIdLength)
  copy.zone_name = `${src.zone_name}${t('zones.copySuffix')}`
  zones.value.push(copy); selectedZoneIndex.value = zones.value.length - 1; hydrateSelectedZone(); dirty.value = true
}
async function deleteSelectedZone() {
  if (zones.value.length <= 1) return
  try { await ElMessageBox.confirm(t('zones.deleteZoneConfirm'), t('zones.deleteZoneTitle'), { type: 'warning' }) } catch { return }
  zones.value.splice(selectedZoneIndex.value, 1); selectedZoneIndex.value = Math.max(0, selectedZoneIndex.value - 1); hydrateSelectedZone(); dirty.value = true
}
function onResolutionChange(prev: SourceResolution, next: SourceResolution) {
  syncSelectedZone()
  zones.value = zones.value.map((zone) => ({ ...zone, polygon: scalePolygonToResolution(zone.polygon, prev, next) }))
  polygonPoints.value = scalePolygonToResolution(polygonPoints.value, prev, next)
  sourceResolution.value = next; dirty.value = true
}

async function saveConfiguration() {
  if (saving.value) return
  saveError.value = ''
  if (!selectedCameraId.value) return ElMessage.warning(t('zones.selectCameraWarning'))
  if (loadedCameraId.value !== selectedCameraId.value) { saveError.value = t('zones.configNotReady'); return ElMessage.warning(saveError.value) }
  saving.value = true
  try {
    syncSelectedZone()
    if (zones.value.some((z) => !z.zone_id.trim() || !z.zone_name.trim() || z.polygon.length < ZONE_GEOMETRY_CONSTANTS.minPolygonPoints)) {
      saveError.value = t('zones.zoneValidationError'); return ElMessage.error(saveError.value)
    }
    if (new Set(zones.value.map((z) => z.zone_id)).size !== zones.value.length) {
      saveError.value = t('zones.duplicateZoneIdError'); return ElMessage.error(saveError.value)
    }
    const res = await updateCameraZones(selectedCameraId.value, {
      expected_version: currentVersion.value > 0 ? currentVersion.value : null,
      source_resolution: sourceResolution.value, ...form, alarm_dwell_threshold_seconds: zoneConfig.alarm_dwell_threshold_seconds, zones: zones.value,
    })
    currentVersion.value = res.config_version
    zones.value = JSON.parse(JSON.stringify(res.zones))
    selectedZoneIndex.value = Math.min(selectedZoneIndex.value, zones.value.length - 1)
    hydrateSelectedZone(); dirty.value = false; clearDraft(selectedCameraId.value)
    ElMessage.success(t('zones.saveSuccess', { version: res.config_version }))
  } catch (err: unknown) {
    const typed = err as { response?: { status?: number; data?: { detail?: string } }; message?: string }
    saveError.value = t('zones.saveFailedPrefix', { detail: typeof typed.response?.data?.detail === 'string' ? typed.response.data.detail : typed.message || t('zones.saveFailedDefault') })
    if (typed.response?.status === 409) {
      void ElMessageBox.confirm(t('zones.conflictMessage'), t('zones.conflictTitle'), { confirmButtonText: t('zones.conflictConfirm'), cancelButtonText: t('common.cancel'), type: 'warning' })
        .then(() => loadCameraConfig()).catch(() => undefined)
    } else ElMessage.error(saveError.value)
  } finally { saving.value = false }
}

const persistCurrentDraft = () => {
  if (!dirty.value || !selectedCameraId.value || hydrating.value || saving.value) return
  saveDraft(selectedCameraId.value, { version: currentVersion.value, zones: displayZones.value, index: selectedZoneIndex.value, resolution: sourceResolution.value, rules: { ...form } })
}
watch(zoneConfig, () => { if (!hydrating.value) dirty.value = true }, { deep: true })
watch([zoneConfig, polygonPoints, zones, sourceResolution, form], persistCurrentDraft, { deep: true, flush: 'post' })
const beforeUnload = (event: BeforeUnloadEvent) => { persistCurrentDraft(); if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
onMounted(() => { void init(); window.addEventListener('beforeunload', beforeUnload) })
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
</script>

<style scoped>
.camera-picker { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.camera-picker .label { font-size: 11px; color: #9a9eae; }
.workspace-grid { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 22px; align-items: start; }
@media (max-width: 1100px) { .workspace-grid { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 650px) { .camera-picker { width: 100%; gap: 8px; } .camera-picker .label { display: none; } }
</style>
