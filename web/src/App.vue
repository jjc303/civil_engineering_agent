<template>
  <div class="app-shell" :class="{ 'monitor-mode': isMonitor, collapsed, 'mobile-open': mobileOpen }">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <button v-if="mobileOpen" class="nav-backdrop" aria-label="关闭导航" @click="mobileOpen = false" />
    <aside class="sidebar" aria-label="工作台导航">
      <router-link to="/dashboard" class="brand" aria-label="施工安全 · 返回监控看板">
        <img class="brand-mark" src="/favicon.svg" width="40" height="40" alt="" />
        <span class="brand-copy"><b>施工安全</b><small>让安全管理更简单</small></span>
      </router-link>
      <div class="nav-caption">工作空间</div>
      <nav><router-link v-for="item in navigation" :key="item.path" :to="item.path" class="nav-item" :title="item.label"><el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span><i /></router-link></nav>
      <div class="sidebar-end">
        <div class="mode-note"><span class="mode-dot" /><span>{{ isMockEnabled ? '演示环境' : '业务工作台' }}<small>{{ isMockEnabled ? '样例数据，未连接现场' : '状态以实际接口返回为准' }}</small></span></div>
        <button class="collapse-button" :aria-label="collapsed ? '展开侧栏' : '收起侧栏'" :aria-expanded="!collapsed" @click="collapsed = !collapsed"><el-icon><Expand v-if="collapsed" /><Fold v-else /></el-icon><span>收起导航</span></button>
      </div>
    </aside>
    <div class="main-shell">
      <header class="topbar">
        <div class="breadcrumb"><button class="mobile-menu" aria-label="打开导航" :aria-expanded="mobileOpen" @click="mobileOpen = !mobileOpen"><el-icon><Menu /></el-icon></button><span class="workspace-name">安全工作台</span><span class="separator">/</span><strong>{{ route.meta.title }}</strong></div>
        <button class="search-trigger" @click="searchOpen = true"><el-icon><Search /></el-icon><span>你想做什么？</span><kbd>Ctrl K</kbd></button><div class="topbar-meta"><span v-if="isMockEnabled || localVideoDemo" class="demo-badge">{{ isMockEnabled ? '演示数据 · 非现场' : '本地视频演示' }}</span><time :datetime="now.toISOString()">{{ dateLabel }}</time><span class="time-label">{{ timeLabel }}</span></div>
      </header>
      <div v-if="navigationFailure" class="navigation-error" role="alert"><span>“{{ navigationFailure.title }}”加载失败，请重新打开。</span><a :href="navigationFailure.path">重新打开页面 ↗</a><button aria-label="关闭加载提示" @click="navigationFailure = null">×</button></div>
      <main id="main-content" tabindex="-1" :class="isMonitor ? 'monitor-content' : 'business-content'"><router-view v-slot="{ Component }"><Transition name="page" mode="out-in"><component :is="Component" /></Transition></router-view></main>
    </div>
    <el-dialog v-model="searchOpen" title="快速前往" width="520px" @opened="searchInput?.focus()" @closed="searchText = ''">
      <input ref="searchInput" v-model="searchText" class="command-input" placeholder="搜索功能，如：视频、整改、助手" aria-label="搜索功能" @keydown.enter="!$event.isComposing && goFirst()" />
      <div class="command-list"><router-link v-for="item in searchResults" :key="item.path" :to="item.path" @click="searchOpen = false"><el-icon><component :is="item.icon" /></el-icon>{{ item.label }}<span>↗</span></router-link><p v-if="!searchResults.length">没有匹配功能，试试“视频”或“整改”。</p></div>
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DataBoard, Warning, DocumentChecked, Crop, VideoCamera, ChatDotRound, Fold, Expand, Menu, Search } from '@element-plus/icons-vue'
import { isMockEnabled } from '@/api/client'
import { navigationFailure } from '@/router'
const route = useRoute()
const router = useRouter()
const searchOpen = ref(false), searchText = ref('')
const searchInput = ref<HTMLInputElement | null>(null)
const searchResults = computed(() => navigation.filter(item => (item.label + (item.path === '/dashboard' ? '视频 看板' : '')).includes(searchText.value.trim())))
function goFirst() { const first = searchResults.value[0]; if (first) { void router.push(first.path); searchOpen.value = false } }
function shortcuts(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); searchOpen.value = !searchOpen.value }
  if (event.key === 'Escape') mobileOpen.value = false
}
onMounted(() => document.addEventListener('keydown', shortcuts))
onUnmounted(() => document.removeEventListener('keydown', shortcuts))
const localVideoDemo = import.meta.env.VITE_LOCAL_VIDEO_DEMO === 'true'
const collapsed = ref(false)
const mobileOpen = ref(false)
const now = ref(new Date())
const isMonitor = computed(() => route.path === '/dashboard')
const dateLabel = computed(() => now.value.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }))
const timeLabel = computed(() => now.value.toLocaleTimeString('zh-CN', { hour12: false }))
const navigation = [
  { path: '/dashboard', label: '现场监控', icon: DataBoard },
  { path: '/violations', label: '违规事件', icon: Warning },
  { path: '/rectification-tasks', label: '整改任务', icon: DocumentChecked },
  { path: '/zones', label: '区域标定', icon: Crop },
  { path: '/cameras', label: '摄像头与节点', icon: VideoCamera },
  { path: '/copilot', label: '安全智能助手', icon: ChatDotRound },
]
let clock: ReturnType<typeof setInterval> | undefined
onMounted(() => { clock = setInterval(() => { now.value = new Date() }, 1000) })
onUnmounted(() => clearInterval(clock))
watch(() => route.path, () => { mobileOpen.value = false })
</script>
<style scoped>

.app-shell { --sidebar-width: 220px; min-height: 100vh; background: #f7f8fc; }
.app-shell.collapsed { --sidebar-width: 80px; }
.sidebar { width: var(--sidebar-width); position: fixed; inset: 0 auto 0 0; z-index: 30; display: flex; flex-direction: column; background: #fff; border-right: 1px solid #edf0f5; transition: width .25s ease; }
.brand { display: flex; align-items: center; gap: 12px; height: 100px; padding: 0 24px; text-decoration: none; white-space: nowrap; }
.brand-mark { width: 40px; height: 40px; flex-shrink: 0; transition: transform .24s cubic-bezier(.2,.8,.2,1); }
.brand:hover .brand-mark { transform: translateY(-2px) rotate(-4deg); }
.brand:active .brand-mark { transform: scale(.94); }
.brand-copy b { display:block; font-size:19px; font-weight:650; letter-spacing:1px; color:#39354f; }.brand-copy small { display:block; margin-top:6px; color:#9297a5; font-size:10px; }
.nav-caption { padding:24px 28px 10px; font-size:11px; color:#9a9fad; }nav{padding:0 14px;}
.nav-item {display:flex; gap:13px; align-items:center; min-height:48px; margin:5px 0; padding:0 15px; text-decoration:none; font-size:14px; color:#677082; border-radius:14px; white-space:nowrap; transition:background .2s,color .2s,transform .2s;}
.nav-item .el-icon{font-size:20px;flex-shrink:0}.nav-item:hover{background:#f5f4fc;color:#6559da;transform:translateX(2px)}.nav-item.router-link-active{background:#edeafe;color:#6559da;font-weight:600}.nav-item i{display:none}
.sidebar-end{margin-top:auto;padding:24px}.mode-note{display:flex;gap:8px;font-size:12px;color:#677082;line-height:1.7}.mode-note small{display:block;font-size:10px;color:#9499a5}.mode-dot{width:6px;height:6px;background:#9b93cc;border-radius:50%;margin-top:8px;flex-shrink:0}.collapse-button{display:flex;gap:10px;align-items:center;border:0;background:none;color:#8a91a0;padding:22px 0 0;font-size:12px}.collapse-button .el-icon{font-size:18px}
.main-shell{margin-left:var(--sidebar-width);min-width:0;transition:margin .25s ease}.topbar{display:flex;align-items:center;gap:24px;min-height:78px;padding:14px 36px;background:#ffffffd9;border-bottom:1px solid #eef0f6}.breadcrumb{display:flex;gap:12px;align-items:center;font-size:13px;color:#8a90a0}.breadcrumb strong{color:#50586a;font-weight:500;white-space:nowrap}.workspace-name,.separator{display:none}.search-trigger{display:flex;align-items:center;gap:10px;background:#f5f6fa;border:1px solid transparent;border-radius:24px;padding:11px 16px;color:#9298a6;min-width:260px;text-align:left;font-size:13px}.search-trigger:hover{border-color:#d9d4f8;background:#f0eefb}.search-trigger kbd{margin-left:auto;font-size:10px;color:#9ea3af}.topbar-meta{margin-left:auto;display:flex;align-items:center;gap:16px;color:#8a91a0;font-size:12px}.time-label{display:none}.demo-badge{font-size:11px;background:#eeeafd;color:#7867bd;padding:6px 10px;border-radius:20px;white-space:nowrap}.business-content{height:calc(100dvh - 78px);overflow:auto;padding:24px}.monitor-content{min-height:calc(100dvh - 78px)}
.collapsed .brand-copy,.collapsed .nav-caption,.collapsed .nav-item span,.collapsed .mode-note,.collapsed .collapse-button span{display:none}.collapsed .brand{padding:0 20px}.collapsed .nav-item{justify-content:center;padding:0}.collapsed .collapse-button{justify-content:center;width:100%}
.mobile-menu,.nav-backdrop{display:none}.skip-link{position:fixed;top:-70px;left:20px;z-index:100;background:white;padding:12px}.skip-link:focus{top:10px}.command-input{width:100%;padding:15px 18px;border:1px solid #e0dcef;border-radius:12px;background:#f8f7fc;font-size:15px;outline-color:#8174dc}.command-list{display:grid;gap:5px;margin-top:14px}.command-list a{display:flex;align-items:center;gap:12px;padding:14px;border-radius:12px;text-decoration:none;color:#5b6271}.command-list a:hover,.command-list a:focus-visible{background:#efecff;color:#6559da}.command-list a span{margin-left:auto}.command-list p{padding:16px;color:#858b98}
.page-enter-active,.page-leave-active{transition:opacity .16s ease,transform .16s ease}.page-enter-from{opacity:0;transform:translateY(6px)}.page-leave-to{opacity:0}
@media(max-width:1150px){.topbar{padding:14px 24px;gap:16px}.search-trigger{min-width:200px}.topbar-meta time{display:none}}
@media(max-width:760px){.app-shell,.app-shell.collapsed{--sidebar-width:0px}.sidebar{width:240px;transform:translateX(-100%);transition:transform .25s ease}.mobile-open .sidebar{transform:translateX(0)}.mobile-open .nav-backdrop{display:block;position:fixed;inset:0;background:#25243f44;border:0;z-index:29;backdrop-filter:blur(3px)}.mobile-menu{display:flex;background:none;border:0;color:#626778;font-size:22px;padding:8px}.topbar{padding:10px 16px;gap:10px;min-height:68px}.breadcrumb strong{display:none}.search-trigger{min-width:0;flex:1;font-size:12px}.search-trigger kbd{display:none}.topbar-meta{gap:0}.demo-badge{font-size:10px;padding:6px 8px}.collapse-button{display:none}.collapsed .brand-copy,.collapsed .nav-item span,.collapsed .mode-note,.collapsed .nav-caption{display:block}.collapsed .nav-item{justify-content:flex-start;padding:0 15px}.business-content{padding:12px;height:calc(100dvh - 68px)}}
.navigation-error{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin:16px 24px 0;padding:14px 18px;background:#fff1e9;border:1px solid #f2d5c1;border-radius:12px;color:#946049;font-size:13px}.navigation-error a{color:#765bbb;text-decoration:underline;text-underline-offset:3px}.navigation-error button{margin-left:auto;border:0;background:none;color:inherit;font-size:20px;padding:2px 8px}
</style>
