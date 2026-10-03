<template>
  <article class="camera-tile" :class="{ 'has-event': activeEventCount > 0 }" :aria-label="`摄像头 ${camera.camera_id}`">
    <div class="frame">
      <img v-if="canPreview && !failed" :key="`${camera.monitor_session_id}-${retry}`" :src="previewUrl(camera.camera_id)" :alt="`${camera.camera_id} 监控预览`" @error="failed = true" />
      <div v-else class="frame-empty">
        <span class="channel-watermark">{{ String(index + 1).padStart(2, '0') }}</span>
        <el-icon><VideoCamera /></el-icon>
        <strong>{{ isMockEnabled ? '演示通道' : !camera.is_online ? '摄像头离线' : !previewAllowed ? '预览已暂停' : '视频暂不可用' }}</strong>
        <span>{{ isMockEnabled ? '样例数据不包含实时画面' : !camera.is_online ? '等待设备上报新的状态' : !previewAllowed ? '返回可见页面后恢复' : '请检查监控会话或重试预览' }}</span>
        <button v-if="failed && canPreview" class="retry-button" @click="retryPreview">重新连接画面</button>
      </div>
      <div class="frame-top"><span class="channel-id">CAM / {{ String(index + 1).padStart(2, '0') }}</span><span v-if="activeEventCount" class="event-count">{{ activeEventCount }} 条列表内活动事件</span></div>
      <div class="frame-bottom"><span><i :class="{ online: camera.is_online && !stale }" />{{ stale ? '状态待更新' : camera.is_online ? '在线' : '离线' }}</span><button :aria-label="`放大 ${camera.camera_id}`" title="放大此路画面" @click="$emit('focus', camera.camera_id)"><el-icon><FullScreen /></el-icon></button></div>
    </div>
    <div class="camera-info"><div class="identity"><b :title="camera.camera_id">{{ locationLabel }}</b><small>{{ camera.camera_id }}</small></div><span class="people-chip">{{ camera.active_workers_count }} 人在画面中</span></div>
    <details class="technical-details"><summary>运行详情 <span>帧率 / 模型 / 上报时间</span></summary><dl class="camera-meta"><div><dt>检测人数</dt><dd>{{ camera.active_workers_count }} <small>人</small></dd></div><div><dt>已处理帧</dt><dd>{{ camera.processed_frame_id.toLocaleString() }}</dd></div><div><dt>最近上报</dt><dd>{{ timeLabel }}</dd></div></dl><p class="model-detail">模型：{{ camera.model_name || '未上报' }} · {{ camera.fps.toFixed(1) }} FPS</p></details>
    <div class="camera-footer"><div><router-link :to="{ path: '/zones', query: { camera_id: camera.camera_id } }">标定区域 ↗</router-link><router-link :to="{ path: '/violations', query: { camera_id: camera.camera_id } }">查看违规 ↗</router-link></div></div>
  </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { VideoCamera, FullScreen } from '@element-plus/icons-vue'
import { previewUrl } from '@/api/cameraManagement'
import { isMockEnabled } from '@/api/client'
import { utcDate } from '@/utils/monitoring'
import type { CameraStatusResponse } from '@/types/contract'

const props = defineProps<{ camera: CameraStatusResponse; index: number; activeEventCount: number; stale: boolean; previewAllowed: boolean }>()
defineEmits<{ focus: [cameraId: string] }>()
const failed = ref(false)
const retry = ref(0)
const canPreview = computed(() => !isMockEnabled && props.camera.is_online && props.previewAllowed)
const locationLabel = computed(() => typeof props.camera.extra_details.location === 'string' ? props.camera.extra_details.location : props.camera.camera_id)
const timeLabel = computed(() => utcDate(props.camera.reported_at_utc).toLocaleTimeString('zh-CN', { hour12: false }))
function retryPreview() { retry.value++; failed.value = false }
watch([() => props.camera.monitor_session_id, () => props.camera.is_online], retryPreview)
</script>

<style scoped>
.camera-tile { background: #19222b; border: 1px solid #ffffff0d; border-radius: 8px; overflow: hidden; min-width: 0; }
.frame { background: #0d1319; aspect-ratio: 16/9; position: relative; overflow: hidden; }
.frame > img { width: 100%; height: 100%; object-fit: contain; display: block; }
.frame-empty { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: #798995; background: radial-gradient(ellipse at 40% 30%, #21303a, #101920 75%); }
.frame-empty > .el-icon { font-size: 25px; color: #5e7381; }
.frame-empty > strong { font-size: 13px; font-weight: 500; color: #afbec6; }
.frame-empty > span:not(.channel-watermark) { font-size: 11px; }
.channel-watermark { position: absolute; font-size: 128px; line-height: 1; font-weight: 700; right: 10px; bottom: -12px; color: #ffffff02; letter-spacing: -10px; pointer-events: none; }
.frame-top, .frame-bottom { position: absolute; left: 12px; right: 12px; display: flex; justify-content: space-between; gap: 8px; align-items: center; pointer-events: none; }
.frame-top { top: 12px; font-size: 9px; letter-spacing: .7px; }
.channel-id { background: #0a131ab3; color: #bbc8cf; padding: 4px 7px; border-radius: 3px; }
.event-count { background: #6c433bdf; color: #f3c7b8; padding: 4px 7px; border-radius: 3px; letter-spacing: 0; }
.frame-bottom { bottom: 10px; color: #d6dfe4; font-size: 10px; }
.frame-bottom > span { padding: 4px 7px; border-radius: 3px; background: #0a131ab3; }
.frame-bottom i { display: inline-block; background: #8c9ba3; width: 5px; height: 5px; border-radius: 50%; margin-right: 5px; }
.frame-bottom i.online { background: #89b2a0; }
.frame-bottom button { display: grid; place-items: center; width: 27px; height: 27px; border: 1px solid #ffffff25; border-radius: 4px; background: #0a131ab3; color: #d6dfe4; pointer-events: auto; }
.camera-info { display: flex; justify-content: space-between; align-items: center; padding: 15px 16px 11px; gap: 10px; }
.identity { overflow: hidden; }.identity b { display: block; color: #dde3e6; font-weight: 500; font-size: 13px; white-space: nowrap; text-overflow: ellipsis; overflow: hidden; }
.identity small { display: block; color: #82929d; font-size: 10px; margin-top: 4px; }
.fps { color: #c9d5dc; font: 17px 'Segoe UI', sans-serif; white-space: nowrap; }.fps small { color: #7c909e; font-size: 9px; }
.camera-meta { display: grid; grid-template-columns: .8fr 1fr 1fr; margin: 0 16px; padding: 11px 0; border-top: 1px solid #ffffff06; gap: 8px; }
.camera-meta dt { font-size: 10px; color: #81929e; margin-bottom: 5px; }.camera-meta dd { font-size: 12px; color: #b4c2cc; margin: 0; font-variant-numeric: tabular-nums; }.camera-meta dd small { font-size: 10px; }
.camera-footer { margin: 0 16px; border-top: 1px solid #ffffff08; padding: 10px 0; display: flex; gap: 12px; justify-content: space-between; align-items: center; font-size: 10px; }
.camera-footer > span { color: #84939d; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.camera-footer > div { display: flex; gap: 12px; flex-shrink: 0; }
.camera-footer a { color: #c9b498; text-decoration: none; }.camera-footer a:hover { color: #eed0a9; }
.retry-button { background: none; color: #dac3a4; border: 1px solid #dac3a440; border-radius: 4px; font-size: 11px; padding: 4px 8px; }
@media (max-width: 440px) { .camera-footer { flex-wrap: wrap; } }

.camera-tile{background:#fff;border:1px solid #eceef5;border-radius:16px;transition:box-shadow .22s,transform .22s}.camera-tile:hover{box-shadow:0 8px 24px #48416212;transform:translateY(-2px)}.frame{border-radius:14px;margin:6px;aspect-ratio:16/10}.frame-bottom button{border-radius:50%;width:34px;height:34px;transition:background .2s,transform .2s}.frame-bottom button:hover{background:#7665cfe0;transform:scale(1.08)}.camera-info{padding:12px 15px}.identity b{color:#666c7e;font-size:13px}.identity small{color:#a4a8b4;font-size:10px}.people-chip{background:#f1eefb;color:#9a8bbd;font-size:10px;white-space:nowrap;border-radius:20px;padding:6px 9px}.camera-footer{border-color:#f0f1f6;justify-content:flex-end;padding:12px 0;margin:0 15px}.camera-footer a{color:#8b7ac1;font-size:11px;border-radius:8px;padding:4px 0}.camera-footer a:hover{color:#6352ac}.technical-details{margin:0 15px;border-top:1px solid #f0f1f6}.technical-details summary{cursor:pointer;font-size:10px;color:#9c9eae;padding:10px 0;list-style:none}.technical-details summary:before{content:'›';display:inline-block;margin-right:7px;transition:transform .2s}.technical-details[open] summary:before{transform:rotate(90deg)}.technical-details summary span{color:#b8bac4;margin-left:8px;font-size:9px}.camera-meta{margin:0;padding:5px 0 10px;border:0}.camera-meta dt{color:#9b9fae}.camera-meta dd{color:#7e8496}.model-detail{color:#9c9eae;font-size:10px;overflow-wrap:anywhere;margin:0 0 10px}.frame-empty{background:linear-gradient(135deg,#eeeef7,#e3e6f0);color:#a0a5b7}.frame-empty>strong{color:#8a91a5}.frame-empty>.el-icon{color:#aba4c9}.frame-empty>span:not(.channel-watermark){font-size:10px}.retry-button{color:#8f7abd;border-color:#d2c5e7;border-radius:20px;padding:5px 12px}

.technical-details summary{font-size:11px;color:#82899a}.identity small{color:#858c9d}.people-chip{color:#81709e}.technical-details summary span{color:#9299a8}.camera-footer a{padding:7px 0}.camera-meta dt{color:#8991a1}
</style>
