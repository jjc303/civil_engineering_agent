<template>
  <div class="camera-management-page">
    <div class="header-section">
      <div><h2>摄像头与 CV 节点</h2><p>配置视频源、分配可用 CV 节点并远程控制监控会话。</p></div>
      <div><el-button :loading="loading" @click="load">刷新节点与会话</el-button><el-button type="primary" :disabled="!adminConfigured" @click="nodeDialogVisible = true">登记 CV 节点</el-button></div>
    </div>

    <el-alert v-if="isMock" title="Mock 模式不提供 CV 调度；切换 VITE_USE_MOCK=false 后配置真实节点。" type="info" :closable="false" />
    <el-alert v-else-if="!adminConfigured" title="缺少 VITE_AGENT_ADMIN_TOKEN，无法进行摄像头与节点管理。" type="warning" :closable="false" />

    <div class="grid">
      <el-card><template #header>可用 CV 节点</template>
        <el-empty v-if="!nodes.length" description="暂无已注册节点；请由管理员先创建节点并在 CV 主机启动 Control 服务。" />
        <el-table v-else :data="nodes" size="small">
          <el-table-column prop="display_name" label="节点" />
          <el-table-column prop="node_id" label="ID" />
          <el-table-column label="状态"><template #default="{ row }"><el-tag :type="row.is_online ? 'success' : 'danger'">{{ row.is_online ? '在线' : '离线' }}</el-tag></template></el-table-column>
          <el-table-column label="负载"><template #default="{ row }">{{ row.active_sessions }}/{{ row.capacity }}</template></el-table-column>
        </el-table>
      </el-card>

      <el-card><template #header>新增摄像头</template>
        <el-form label-position="top" @submit.prevent="createCamera">
          <el-form-item label="摄像头 ID"><el-input v-model="form.camera_id" placeholder="cam-field-01" /></el-form-item>
          <el-form-item label="显示名称"><el-input v-model="form.display_name" placeholder="东侧塔吊" /></el-form-item>
          <el-form-item label="CV 节点"><el-select v-model="form.node_id" style="width:100%" placeholder="选择在线节点" @change="clearFileSource(form)"><el-option v-for="node in onlineNodes" :key="node.node_id" :label="`${node.display_name} (${node.node_id})`" :value="node.node_id" /></el-select></el-form-item>
          <el-form-item label="视频源类型"><el-radio-group v-model="form.source_type" @change="clearFileSource(form)"><el-radio value="rtsp">RTSP</el-radio><el-radio value="file">节点本地文件</el-radio></el-radio-group></el-form-item>
          <el-form-item :label="form.source_type === 'rtsp' ? 'RTSP 地址' : 'CV 节点本地文件'"><el-input v-model="form.source_uri" :readonly="form.source_type === 'file'" :type="form.source_type === 'rtsp' ? 'password' : 'text'" show-password placeholder="rtsp://user:password@host/live"><template v-if="form.source_type === 'file'" #append><el-button :disabled="!form.node_id" @click="openMediaBrowser('create')">选择文件</el-button></template></el-input></el-form-item>
          <el-button type="primary" :loading="creating" :disabled="!adminConfigured" @click="createCamera">保存摄像头</el-button>
        </el-form>
      </el-card>
    </div>

    <el-card class="camera-list"><template #header>已配置摄像头</template>
      <el-table :data="cameras" v-loading="loading">
        <el-table-column prop="display_name" label="名称" /><el-table-column prop="camera_id" label="ID" /><el-table-column prop="node_id" label="CV 节点" />
        <el-table-column prop="source_uri_masked" label="视频源（脱敏）" min-width="220" show-overflow-tooltip />
        <el-table-column label="会话"><template #default="{ row }"><el-tag :type="row.desired_state === 'RUNNING' ? 'success' : 'info'">{{ row.desired_state === 'RUNNING' ? '运行中' : '已停止' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="280"><template #default="{ row }"><el-button size="small" :disabled="!adminConfigured" @click="openEdit(row)">编辑</el-button><el-button size="small" type="primary" :disabled="!adminConfigured || row.desired_state === 'RUNNING'" @click="control(row.camera_id, 'start')">启动</el-button><el-button size="small" :disabled="!adminConfigured || row.desired_state === 'STOPPED'" @click="control(row.camera_id, 'stop')">停止</el-button><el-button size="small" :disabled="row.desired_state !== 'RUNNING'" @click="openPreview(row.camera_id)">预览</el-button></template></el-table-column>
      </el-table>
    </el-card>
    <el-dialog v-model="editDialogVisible" title="编辑摄像头配置" width="560px" destroy-on-close>
      <el-alert v-if="editingCamera?.desired_state === 'RUNNING'" title="保存时会先停止当前监控会话；修改完成后请重新启动。" type="warning" :closable="false" class="dialog-alert" />
      <el-form label-position="top">
        <el-form-item label="摄像头 ID"><el-input v-model="editForm.camera_id" disabled /></el-form-item>
        <el-form-item label="显示名称"><el-input v-model="editForm.display_name" /></el-form-item>
        <el-form-item label="CV 节点"><el-select v-model="editForm.node_id" style="width:100%" @change="clearFileSource(editForm)"><el-option v-for="node in onlineNodes" :key="node.node_id" :label="`${node.display_name} (${node.node_id})`" :value="node.node_id" /></el-select></el-form-item>
        <el-form-item label="视频源类型"><el-radio-group v-model="editForm.source_type" @change="clearFileSource(editForm)"><el-radio value="rtsp">RTSP</el-radio><el-radio value="file">节点本地文件</el-radio></el-radio-group></el-form-item>
        <el-form-item :label="editForm.source_type === 'rtsp' ? '新的 RTSP 地址（可不填）' : '新的 CV 节点本地文件（可不改）'"><el-input v-model="editForm.source_uri" :readonly="editForm.source_type === 'file'" :type="editForm.source_type === 'rtsp' ? 'password' : 'text'" show-password :placeholder="editForm.source_uri_masked || '不填写则保留原视频源'"><template v-if="editForm.source_type === 'file'" #append><el-button :disabled="!editForm.node_id" @click="openMediaBrowser('edit')">选择文件</el-button></template></el-input><div class="source-hint">为保护凭据，原始视频地址不会回显。只修改名称时可保持为空。</div></el-form-item>
      </el-form>
      <template #footer><el-button @click="editDialogVisible = false">取消</el-button><el-button type="primary" :loading="savingEdit" @click="saveEdit">保存修改</el-button></template>
    </el-dialog>
    <el-dialog v-model="mediaBrowserVisible" title="选择 CV 节点本地视频文件" width="760px" destroy-on-close>
      <el-alert title="这里展示的是所选 CV 节点的允许媒体目录，而非浏览器所在电脑的文件系统。" type="info" :closable="false" class="dialog-alert" />
      <div class="media-path">当前目录：{{ mediaDirectory?.current_path || '加载中…' }}</div><el-button size="small" :disabled="!mediaDirectory?.parent_path || browsingMedia" @click="browseMedia(mediaDirectory?.parent_path || undefined)">返回上级</el-button>
      <el-table v-loading="browsingMedia" :data="mediaDirectory?.directories || []" class="media-table" empty-text="当前目录没有子目录"><el-table-column prop="name" label="文件夹" /><el-table-column width="120"><template #default="{ row }"><el-button size="small" @click="browseMedia(row.path)">打开</el-button></template></el-table-column></el-table>
      <el-table v-loading="browsingMedia" :data="mediaDirectory?.files || []" class="media-table" empty-text="当前目录没有支持的视频文件"><el-table-column prop="name" label="视频文件" /><el-table-column width="120"><template #default="{ row }"><el-button size="small" type="primary" @click="selectMediaFile(row.path)">选择</el-button></template></el-table-column></el-table>
    </el-dialog>
    <el-dialog v-model="previewVisible" title="实时 MJPEG 预览" width="760px" destroy-on-close><img v-if="previewCameraId" class="preview" :src="previewUrl(previewCameraId)" alt="摄像头预览" /></el-dialog>
    <el-dialog v-model="nodeDialogVisible" title="登记 CV Control 节点" width="520px"><el-form label-position="top"><el-form-item label="节点 ID"><el-input v-model="nodeForm.node_id" placeholder="cv-east-01" /></el-form-item><el-form-item label="显示名称"><el-input v-model="nodeForm.display_name" placeholder="东区 GPU 节点" /></el-form-item><el-form-item label="Control URL"><el-input v-model="nodeForm.control_url" placeholder="http://cv-host:8100" /></el-form-item><el-form-item label="并发容量"><el-input-number v-model="nodeForm.capacity" :min="1" :max="128" /></el-form-item></el-form><template #footer><el-button @click="nodeDialogVisible = false">取消</el-button><el-button type="primary" :loading="creatingNode" @click="createNode">登记并获取令牌</el-button></template></el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createCvNode, createManagedCamera, fetchCvNodes, fetchManagedCameras, fetchNodeMediaFiles, previewUrl, setMonitoring, updateManagedCamera } from '@/api/cameraManagement'
import type { CvNodeMediaDirectory } from '@/api/cameraManagement'
import { isMockEnabled } from '@/api/client'
import type { CvNodeResponse, ManagedCameraResponse } from '@/types/contract'

const nodes = ref<CvNodeResponse[]>([]); const cameras = ref<ManagedCameraResponse[]>([])
const loading = ref(false); const creating = ref(false); const creatingNode = ref(false); const nodeDialogVisible = ref(false); const previewVisible = ref(false); const previewCameraId = ref('')
const editDialogVisible = ref(false); const savingEdit = ref(false); const editingCamera = ref<ManagedCameraResponse | null>(null)
const mediaBrowserVisible = ref(false); const browsingMedia = ref(false); const mediaDirectory = ref<CvNodeMediaDirectory | null>(null); const mediaTarget = ref<'create' | 'edit'>('create'); const mediaNodeId = ref('')
const isMock = isMockEnabled; const adminConfigured = Boolean(import.meta.env.VITE_AGENT_ADMIN_TOKEN)
const onlineNodes = computed(() => nodes.value.filter((node) => node.is_online))
type CameraForm = { camera_id: string; display_name: string; node_id: string; source_type: 'rtsp' | 'file'; source_uri: string; source_uri_masked?: string }
const form = reactive<CameraForm>({ camera_id: '', display_name: '', node_id: '', source_type: 'rtsp', source_uri: '' })
const editForm = reactive<CameraForm>({ camera_id: '', display_name: '', node_id: '', source_type: 'rtsp', source_uri: '' })
const nodeForm = reactive({ node_id: '', display_name: '', control_url: '', capacity: 8 })

async function load() { loading.value = true; try { [nodes.value, cameras.value] = await Promise.all([fetchCvNodes(), fetchManagedCameras()]) } catch { ElMessage.error('无法获取 CV 节点或摄像头配置，请检查 Agent 管理令牌和服务连接。') } finally { loading.value = false } }
function clearFileSource(target: CameraForm) { target.source_uri = '' }
async function createCamera() { if (!form.camera_id || !form.display_name || !form.node_id || !form.source_uri) return ElMessage.warning('请完整填写摄像头配置'); creating.value = true; try { await createManagedCamera({ ...form }); ElMessage.success('摄像头已保存，视频源已脱敏保存。'); form.camera_id = ''; form.display_name = ''; form.source_uri = ''; await load() } catch { /* Axios interceptor already reports the error. */ } finally { creating.value = false } }
function openEdit(camera: ManagedCameraResponse) { editingCamera.value = camera; Object.assign(editForm, { camera_id: camera.camera_id, display_name: camera.display_name, node_id: camera.node_id, source_type: camera.source_type, source_uri: '', source_uri_masked: camera.source_uri_masked }); editDialogVisible.value = true }
async function saveEdit() {
  if (!editingCamera.value || !editForm.display_name || !editForm.node_id) return ElMessage.warning('请完整填写摄像头配置')
  const targetChanged = editForm.node_id !== editingCamera.value.node_id || editForm.source_type !== editingCamera.value.source_type
  if (targetChanged && !editForm.source_uri) return ElMessage.warning('变更 CV 节点或视频源类型时，请重新选择视频源')
  savingEdit.value = true
  try {
    if (editingCamera.value.desired_state === 'RUNNING') {
      await ElMessageBox.confirm('保存前会停止正在运行的监控，保存后请手动重新启动。是否继续？', '修改运行中摄像头', { type: 'warning' })
      await setMonitoring(editingCamera.value.camera_id, 'stop')
    }
    await updateManagedCamera(editForm.camera_id, { display_name: editForm.display_name, node_id: editForm.node_id, source_type: editForm.source_type, ...(editForm.source_uri ? { source_uri: editForm.source_uri } : {}) })
    ElMessage.success('摄像头配置已更新'); editDialogVisible.value = false; await load()
  } catch { /* Axios interceptor already reports the error. */ } finally { savingEdit.value = false }
}
async function createNode() { if (!nodeForm.node_id || !nodeForm.display_name || !nodeForm.control_url) return ElMessage.warning('请完整填写节点配置'); creatingNode.value = true; try { const node = await createCvNode({ ...nodeForm }); nodeDialogVisible.value = false; await ElMessageBox.alert(`请立即复制并仅保存一次：\n\nCV_NODE_ID=${node.node_id}\nCV_NODE_TOKEN=${node.control_token}`, 'CV 节点专属令牌', { confirmButtonText: '已安全保存', closeOnClickModal: false }); await load() } catch { /* Axios interceptor already reports the error. */ } finally { creatingNode.value = false } }
async function control(cameraId: string, action: 'start'|'stop') { try { await setMonitoring(cameraId, action); ElMessage.success(action === 'start' ? '已提交启动请求' : '已提交停止请求'); await load() } catch { /* Axios interceptor already reports the error. */ } }
function openPreview(cameraId: string) { previewCameraId.value = cameraId; previewVisible.value = true }
async function openMediaBrowser(target: 'create' | 'edit') { const current = target === 'create' ? form : editForm; if (!current.node_id) return ElMessage.warning('请先选择 CV 节点'); mediaTarget.value = target; mediaNodeId.value = current.node_id; mediaBrowserVisible.value = true; await browseMedia() }
async function browseMedia(directory?: string) { browsingMedia.value = true; try { mediaDirectory.value = await fetchNodeMediaFiles(mediaNodeId.value, directory) } catch { /* Axios interceptor already reports the error. */ } finally { browsingMedia.value = false } }
function selectMediaFile(path: string) { const target = mediaTarget.value === 'create' ? form : editForm; target.source_uri = path; mediaBrowserVisible.value = false }
onMounted(load)
</script>

<style scoped>
.camera-management-page{padding:24px;overflow-y:auto;height:100%}.header-section{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px}.header-section h2{margin:0;color:#0f172a}.header-section p{color:#64748b;margin:6px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:16px 0}.camera-list{margin-top:20px}.preview{display:block;width:100%;min-height:320px;background:#0f172a;object-fit:contain}.dialog-alert{margin-bottom:16px}.source-hint{font-size:12px;line-height:20px;color:#64748b}.media-path{margin:0 0 12px;color:#475569;word-break:break-all}.media-table{margin-top:12px}@media(max-width:900px){.grid{grid-template-columns:1fr}}
</style>
