<template>
  <div class="camera-management-page operations-workbench">
    <WorkspaceIntro eyebrow="CAMERAS & NODES" :title="t('cameras.title')" :description="t('cameras.description')">
      <el-button :loading="loading" @click="load">{{ t('cameras.refreshDevices') }}</el-button><el-button @click="nodeDialogVisible = true">{{ t('cameras.registerNode') }}</el-button><el-button type="primary" @click="cameraDialogVisible = true">{{ t('cameras.addCamera') }}</el-button>
    </WorkspaceIntro>
    <WorkspaceSummary :label="t('cameras.summaryLabel')" :items="summaryItems" />

    <el-alert v-if="isMock" :title="t('cameras.mockNotice')" type="info" :closable="false" />

    <el-card class="camera-list"><template #header><div class="section-card-heading"><strong>{{ t('cameras.cameraListTitle') }}</strong><span>{{ t('cameras.cameraListSubtitle', { count: dataLoaded ? cameras.length : '—' }) }}</span></div></template>
      <div class="camera-list-filters"><el-input v-model="cameraQuery" clearable :placeholder="t('cameras.searchPlaceholder')" :aria-label="t('cameras.searchPlaceholder')" /><el-radio-group v-model="sourceFilter" size="small" :aria-label="t('cameras.sourceFilterAria')"><el-radio-button value="all">{{ t('cameras.sourceAll') }}</el-radio-button><el-radio-button value="rtsp">{{ t('cameras.sourceRtsp') }}</el-radio-button><el-radio-button value="file">{{ t('cameras.sourceFile') }}</el-radio-button></el-radio-group></div>
      <el-table :data="filteredCameras" v-loading="loading" :empty-text="t('cameras.emptyCameras')">
        <el-table-column prop="display_name" :label="t('cameras.colName')" min-width="190" show-overflow-tooltip /><el-table-column prop="camera_id" :label="t('cameras.colId')" width="140" /><el-table-column prop="node_id" :label="t('cameras.colNode')" width="160" />
        <el-table-column prop="source_uri_masked" :label="t('cameras.colSource')" min-width="220" show-overflow-tooltip />
        <el-table-column :label="t('cameras.colSession')" width="105"><template #default="{ row }"><el-tag :type="row.desired_state === 'RUNNING' ? 'success' : 'info'">{{ row.desired_state === 'RUNNING' ? t('cameras.stateRunning') : t('cameras.stateStopped') }}</el-tag></template></el-table-column>
        <el-table-column :label="t('cameras.colActions')" width="280"><template #default="{ row }"><el-button size="small" @click="openEdit(row)">{{ t('cameras.actionEdit') }}</el-button><el-button size="small" type="primary" :disabled="row.desired_state === 'RUNNING'" @click="control(row.camera_id, 'start')">{{ t('cameras.actionStart') }}</el-button><el-button size="small" :disabled="row.desired_state === 'STOPPED'" @click="control(row.camera_id, 'stop')">{{ t('cameras.actionStop') }}</el-button><el-button size="small" :disabled="row.desired_state !== 'RUNNING'" @click="openPreview(row.camera_id)">{{ t('cameras.actionPreview') }}</el-button></template></el-table-column>
      </el-table>
      <p class="table-scroll-hint">{{ t('cameras.scrollHint') }}</p>
    </el-card>
    <div class="grid">
      <el-card><template #header><div class="section-card-heading"><strong>{{ t('cameras.nodesTitle') }}</strong><span>{{ t('cameras.nodesSubtitle') }}</span></div></template>
        <el-empty v-if="!nodes.length" :description="t('cameras.emptyNodes')" />
        <el-table v-else :data="nodes" size="small">
          <el-table-column prop="display_name" :label="t('cameras.colNodeName')" />
          <el-table-column prop="node_id" :label="t('cameras.colNodeId')" />
          <el-table-column :label="t('cameras.colNodeStatus')" min-width="110"><template #default="{ row }"><el-tag :type="!row.is_online ? 'danger' : row.active_sessions > row.capacity ? 'warning' : 'success'">{{ !row.is_online ? t('cameras.nodeOffline') : row.active_sessions > row.capacity ? t('cameras.nodeOverloaded') : t('cameras.nodeOnline') }}</el-tag></template></el-table-column>
          <el-table-column :label="t('cameras.colLoad')" min-width="155"><template #default="{ row }">{{ row.active_sessions }}/{{ row.capacity }}<small v-if="row.active_sessions > row.capacity" style="display:block;color:#b7791f">{{ t('cameras.overloadHint', { count: row.active_sessions - row.capacity }) }}</small></template></el-table-column>
        </el-table>
      </el-card>

      <section class="device-guide"><span>{{ t('cameras.guideEyebrow') }}</span><h3>{{ t('cameras.guideTitleLine1') }}<br />{{ t('cameras.guideTitleLine2') }}</h3><ol><li><b>01</b>{{ t('cameras.guideStep1') }}</li><li><b>02</b>{{ t('cameras.guideStep2') }}</li><li><b>03</b>{{ t('cameras.guideStep3') }}</li></ol><router-link to="/dashboard">{{ t('cameras.guideAction') }} <span>↗</span></router-link></section>
    </div>
    <el-dialog v-model="cameraDialogVisible" :title="t('cameras.createCameraTitle')" width="600px">
      <p class="dialog-description">{{ t('cameras.createCameraDesc') }}</p>
        <el-form label-position="top" @submit.prevent="createCamera">
          <el-form-item :label="t('cameras.fieldCameraId')"><el-input v-model="form.camera_id" placeholder="cam-field-01" /></el-form-item>
          <el-form-item :label="t('cameras.fieldDisplayName')"><el-input v-model="form.display_name" :placeholder="t('cameras.fieldDisplayNamePlaceholder')" /></el-form-item>
          <el-form-item :label="t('cameras.fieldCvNode')"><el-select v-model="form.node_id" style="width:100%" :placeholder="t('cameras.selectOnlineNode')" @change="clearFileSource(form)"><el-option v-for="node in onlineNodes" :key="node.node_id" :label="`${node.display_name} (${node.node_id})`" :value="node.node_id" /></el-select></el-form-item>
          <el-form-item :label="t('cameras.fieldSourceType')"><el-radio-group v-model="form.source_type" @change="clearFileSource(form)"><el-radio value="rtsp">RTSP</el-radio><el-radio value="file">{{ t('cameras.sourceLocalFile') }}</el-radio></el-radio-group></el-form-item>
          <el-form-item :label="form.source_type === 'rtsp' ? t('cameras.fieldRtspUrl') : t('cameras.fieldLocalFile')"><el-input v-model="form.source_uri" :readonly="form.source_type === 'file'" :type="form.source_type === 'rtsp' ? 'password' : 'text'" show-password placeholder="rtsp://user:password@host/live"><template v-if="form.source_type === 'file'" #append><el-button :disabled="!form.node_id" @click="openMediaBrowser('create')">{{ t('cameras.chooseFile') }}</el-button></template></el-input></el-form-item>
          <el-button type="primary" :loading="creating" @click="createCamera">{{ t('cameras.saveCamera') }}</el-button>
        </el-form>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" :title="t('cameras.editCameraTitle')" width="560px" destroy-on-close>
      <el-alert v-if="editingCamera?.desired_state === 'RUNNING'" :title="t('cameras.editRunningAlert')" type="warning" :closable="false" class="dialog-alert" />
      <el-form label-position="top">
        <el-form-item :label="t('cameras.fieldCameraId')"><el-input v-model="editForm.camera_id" disabled /></el-form-item>
        <el-form-item :label="t('cameras.fieldDisplayName')"><el-input v-model="editForm.display_name" /></el-form-item>
        <el-form-item :label="t('cameras.fieldCvNode')"><el-select v-model="editForm.node_id" style="width:100%" @change="clearFileSource(editForm)"><el-option v-for="node in onlineNodes" :key="node.node_id" :label="`${node.display_name} (${node.node_id})`" :value="node.node_id" /></el-select></el-form-item>
        <el-form-item :label="t('cameras.fieldSourceType')"><el-radio-group v-model="editForm.source_type" @change="clearFileSource(editForm)"><el-radio value="rtsp">RTSP</el-radio><el-radio value="file">{{ t('cameras.sourceLocalFile') }}</el-radio></el-radio-group></el-form-item>
        <el-form-item :label="editForm.source_type === 'rtsp' ? t('cameras.fieldNewRtsp') : t('cameras.fieldNewLocalFile')"><el-input v-model="editForm.source_uri" :readonly="editForm.source_type === 'file'" :type="editForm.source_type === 'rtsp' ? 'password' : 'text'" show-password :placeholder="editForm.source_uri_masked || t('cameras.keepOldSourcePlaceholder')"><template v-if="editForm.source_type === 'file'" #append><el-button :disabled="!editForm.node_id" @click="openMediaBrowser('edit')">{{ t('cameras.chooseFile') }}</el-button></template></el-input><div class="source-hint">{{ t('cameras.sourceMaskHint') }}</div></el-form-item>
      </el-form>
      <template #footer><el-button @click="editDialogVisible = false">{{ t('common.cancel') }}</el-button><el-button type="primary" :loading="savingEdit" @click="saveEdit">{{ t('cameras.saveChanges') }}</el-button></template>
    </el-dialog>
    <el-dialog v-model="mediaBrowserVisible" :title="t('cameras.mediaBrowserTitle')" width="760px" destroy-on-close>
      <el-alert :title="t('cameras.mediaBrowserAlert')" type="info" :closable="false" class="dialog-alert" />
      <div class="media-path">{{ t('cameras.currentDir', { path: mediaDirectory?.current_path || t('common.loading') }) }}</div><el-button size="small" :disabled="!mediaDirectory?.parent_path || browsingMedia" @click="browseMedia(mediaDirectory?.parent_path || undefined)">{{ t('cameras.goParentDir') }}</el-button>
      <el-table v-loading="browsingMedia" :data="mediaDirectory?.directories || []" class="media-table" :empty-text="t('cameras.emptyDirs')"><el-table-column prop="name" :label="t('cameras.colFolder')" /><el-table-column width="120"><template #default="{ row }"><el-button size="small" @click="browseMedia(row.path)">{{ t('cameras.openDir') }}</el-button></template></el-table-column></el-table>
      <el-table v-loading="browsingMedia" :data="mediaDirectory?.files || []" class="media-table" :empty-text="t('cameras.emptyFiles')"><el-table-column prop="name" :label="t('cameras.colVideoFile')" /><el-table-column width="120"><template #default="{ row }"><el-button size="small" type="primary" @click="selectMediaFile(row.path)">{{ t('cameras.selectFile') }}</el-button></template></el-table-column></el-table>
    </el-dialog>
    <el-dialog v-model="previewVisible" :title="t('cameras.previewTitle')" width="760px" destroy-on-close><img v-if="previewCameraId" class="preview" :src="previewUrl(previewCameraId)" :alt="t('cameras.previewAlt')" /></el-dialog>
    <el-dialog v-model="nodeDialogVisible" :title="t('cameras.registerNodeTitle')" width="520px"><el-form label-position="top"><el-form-item :label="t('cameras.fieldNodeId')"><el-input v-model="nodeForm.node_id" placeholder="cv-east-01" /></el-form-item><el-form-item :label="t('cameras.fieldDisplayName')"><el-input v-model="nodeForm.display_name" :placeholder="t('cameras.fieldNodeNamePlaceholder')" /></el-form-item><el-form-item :label="t('cameras.fieldControlUrl')"><el-input v-model="nodeForm.control_url" placeholder="http://cv-host:8100" /></el-form-item><el-form-item :label="t('cameras.fieldCapacity')"><el-input-number v-model="nodeForm.capacity" :min="1" :max="128" /></el-form-item></el-form><template #footer><el-button @click="nodeDialogVisible = false">{{ t('common.cancel') }}</el-button><el-button type="primary" :loading="creatingNode" @click="createNode">{{ t('cameras.registerAndGetToken') }}</el-button></template></el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createCvNode, createManagedCamera, fetchCvNodes, fetchManagedCameras, fetchNodeMediaFiles, previewUrl, setMonitoring, updateManagedCamera } from '@/api/cameraManagement'
import type { CvNodeMediaDirectory } from '@/api/cameraManagement'
import { isMockEnabled } from '@/api/client'
import type { CvNodeResponse, ManagedCameraResponse } from '@/types/contract'
import WorkspaceIntro from '@/components/WorkspaceIntro.vue'
import WorkspaceSummary from '@/components/WorkspaceSummary.vue'
import { useAppI18n } from '@/i18n/useAppI18n'

const { t } = useAppI18n()
const nodes = ref<CvNodeResponse[]>([]); const cameras = ref<ManagedCameraResponse[]>([])
const loading = ref(false); const creating = ref(false); const creatingNode = ref(false); const nodeDialogVisible = ref(false); const previewVisible = ref(false); const previewCameraId = ref('')
const editDialogVisible = ref(false); const savingEdit = ref(false); const editingCamera = ref<ManagedCameraResponse | null>(null)
const mediaBrowserVisible = ref(false); const browsingMedia = ref(false); const mediaDirectory = ref<CvNodeMediaDirectory | null>(null); const mediaTarget = ref<'create' | 'edit'>('create'); const mediaNodeId = ref('')
const isMock = isMockEnabled
const onlineNodes = computed(() => nodes.value.filter((node) => node.is_online))
const cameraDialogVisible = ref(false), dataLoaded = ref(false), cameraQuery = ref(''), sourceFilter = ref<'all' | 'rtsp' | 'file'>('all')
const filteredCameras = computed(() => cameras.value.filter(camera => (sourceFilter.value === 'all' || camera.source_type === sourceFilter.value) && `${camera.display_name} ${camera.camera_id}`.toLowerCase().includes(cameraQuery.value.trim().toLowerCase())))
const summaryItems = computed(() => [
  { label: t('cameras.summaryRegistered'), value: dataLoaded.value ? cameras.value.length : '—', hint: t('cameras.summaryRegisteredHint') },
  { label: t('cameras.summaryOnlineNodes'), value: dataLoaded.value ? onlineNodes.value.length : '—', hint: t('cameras.summaryOnlineNodesHint'), tone: 'success' as const },
  { label: t('cameras.summaryCapacity'), value: dataLoaded.value ? `${onlineNodes.value.reduce((sum, node) => sum + node.active_sessions, 0)} / ${onlineNodes.value.reduce((sum, node) => sum + node.capacity, 0)}` : '—', hint: t('cameras.summaryCapacityHint'), tone: onlineNodes.value.some(node => node.active_sessions > node.capacity) ? 'warning' as const : undefined },
])
type CameraForm = { camera_id: string; display_name: string; node_id: string; source_type: 'rtsp' | 'file'; source_uri: string; source_uri_masked?: string }
const form = reactive<CameraForm>({ camera_id: '', display_name: '', node_id: '', source_type: 'rtsp', source_uri: '' })
const editForm = reactive<CameraForm>({ camera_id: '', display_name: '', node_id: '', source_type: 'rtsp', source_uri: '' })
const nodeForm = reactive({ node_id: '', display_name: '', control_url: '', capacity: 8 })

async function load() { loading.value = true; try { [nodes.value, cameras.value] = await Promise.all([fetchCvNodes(), fetchManagedCameras()]); dataLoaded.value = true } catch { ElMessage.error(t('cameras.fetchError')) } finally { loading.value = false } }
function clearFileSource(target: CameraForm) { target.source_uri = '' }
async function createCamera() { if (!form.camera_id || !form.display_name || !form.node_id || !form.source_uri) return ElMessage.warning(t('cameras.incompleteCameraWarning')); creating.value = true; try { await createManagedCamera({ ...form }); ElMessage.success(t('cameras.cameraCreatedSuccess')); form.camera_id = ''; form.display_name = ''; form.source_uri = ''; cameraDialogVisible.value = false; await load() } catch { /* Axios interceptor already reports the error. */ } finally { creating.value = false } }
function openEdit(camera: ManagedCameraResponse) { editingCamera.value = camera; Object.assign(editForm, { camera_id: camera.camera_id, display_name: camera.display_name, node_id: camera.node_id, source_type: camera.source_type, source_uri: '', source_uri_masked: camera.source_uri_masked }); editDialogVisible.value = true }
async function saveEdit() {
  if (!editingCamera.value || !editForm.display_name || !editForm.node_id) return ElMessage.warning(t('cameras.incompleteCameraWarning'))
  const targetChanged = editForm.node_id !== editingCamera.value.node_id || editForm.source_type !== editingCamera.value.source_type
  if (targetChanged && !editForm.source_uri) return ElMessage.warning(t('cameras.sourceChangeWarning'))
  savingEdit.value = true
  try {
    if (editingCamera.value.desired_state === 'RUNNING') {
      await ElMessageBox.confirm(t('cameras.runningEditConfirm'), t('cameras.runningEditTitle'), { type: 'warning' })
      await setMonitoring(editingCamera.value.camera_id, 'stop')
    }
    await updateManagedCamera(editForm.camera_id, { display_name: editForm.display_name, node_id: editForm.node_id, source_type: editForm.source_type, ...(editForm.source_uri ? { source_uri: editForm.source_uri } : {}) })
    ElMessage.success(t('cameras.cameraUpdatedSuccess')); editDialogVisible.value = false; await load()
  } catch { /* Axios interceptor already reports the error. */ } finally { savingEdit.value = false }
}
async function createNode() { if (!nodeForm.node_id || !nodeForm.display_name || !nodeForm.control_url) return ElMessage.warning(t('cameras.incompleteNodeWarning')); creatingNode.value = true; try { const node = await createCvNode({ ...nodeForm }); nodeDialogVisible.value = false; await ElMessageBox.alert(t('cameras.nodeTokenBody', { nodeId: node.node_id, token: node.control_token }), t('cameras.nodeTokenTitle'), { confirmButtonText: t('cameras.nodeTokenSaved'), closeOnClickModal: false }); await load() } catch { /* Axios interceptor already reports the error. */ } finally { creatingNode.value = false } }
async function control(cameraId: string, action: 'start'|'stop') { try { await setMonitoring(cameraId, action); ElMessage.success(action === 'start' ? t('cameras.startRequested') : t('cameras.stopRequested')); await load() } catch { /* Axios interceptor already reports the error. */ } }
function openPreview(cameraId: string) { previewCameraId.value = cameraId; previewVisible.value = true }
async function openMediaBrowser(target: 'create' | 'edit') { const current = target === 'create' ? form : editForm; if (!current.node_id) return ElMessage.warning(t('cameras.selectNodeFirst')); mediaTarget.value = target; mediaNodeId.value = current.node_id; mediaBrowserVisible.value = true; await browseMedia() }
async function browseMedia(directory?: string) { browsingMedia.value = true; try { mediaDirectory.value = await fetchNodeMediaFiles(mediaNodeId.value, directory) } catch { /* Axios interceptor already reports the error. */ } finally { browsingMedia.value = false } }
function selectMediaFile(path: string) { const target = mediaTarget.value === 'create' ? form : editForm; target.source_uri = path; mediaBrowserVisible.value = false }
onMounted(load)
</script>

<style scoped>
.grid{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:22px;margin-top:24px;align-items:start}.camera-list-filters{display:flex;align-items:center;gap:16px;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap}.camera-list-filters>.el-input{width:290px;max-width:100%}.device-guide{padding:28px;border-radius:20px;background:linear-gradient(148deg,#6355be,#8c77d8);color:#fff}.device-guide>span{font-size:11px;color:#e0d9f5}.device-guide h3{font-size:23px;font-weight:600;line-height:1.5;margin:13px 0 24px}.device-guide ol{padding:0;list-style:none;margin:0;display:grid;gap:17px;font-size:12px;color:#e9e4f6}.device-guide li{display:flex;align-items:center;gap:12px}.device-guide b{font-size:10px;padding:6px 7px;border:1px solid #ffffff2a;border-radius:7px;font-weight:400}.device-guide>a{display:flex;justify-content:space-between;margin-top:27px;padding-top:17px;border-top:1px solid #ffffff24;font-size:12px;text-decoration:none;color:#fff}.preview{display:block;width:100%;min-height:320px;background:#141a21;object-fit:contain;border-radius:12px}.dialog-alert{margin-bottom:16px}.source-hint,.dialog-description{font-size:12px;line-height:1.8;color:#9298a8}.dialog-description{margin:0 0 22px}.media-path{margin:0 0 12px;color:#798196;word-break:break-all}.media-table{margin-top:12px}@media(max-width:900px){.grid{grid-template-columns:minmax(0,1fr)}.device-guide{display:none}}@media(max-width:600px){.camera-list-filters{gap:12px}.camera-list-filters>.el-input{width:100%}}
</style>
