<template>
  <div class="app-layout">
    <!-- 左侧导航栏 -->
    <aside class="sidebar">
      <div class="brand">
        <el-icon :size="24" class="brand-icon"><Platform /></el-icon>
        <div class="brand-text">
          <span class="main-title">智慧施工安全中枢</span>
          <span class="sub-title">Smart Safety Agent</span>
        </div>
      </div>

      <nav class="nav-menu">
        <router-link to="/dashboard" class="nav-item" active-class="active">
          <el-icon><DataBoard /></el-icon>
          <span>监控态势看板</span>
        </router-link>

        <router-link to="/violations" class="nav-item" active-class="active">
          <el-icon><Warning /></el-icon>
          <span>违规事件中心</span>
        </router-link>

        <router-link to="/zones" class="nav-item" active-class="active">
          <el-icon><Crop /></el-icon>
          <span>危险区域标定</span>
        </router-link>

        <router-link to="/cameras" class="nav-item" active-class="active">
          <el-icon><VideoCamera /></el-icon>
          <span>摄像头与 CV 节点</span>
        </router-link>

        <router-link to="/copilot" class="nav-item" active-class="active">
          <el-icon><ChatDotRound /></el-icon>
          <span>安全智能助手</span>
        </router-link>
      </nav>

      <!-- 底部网络/环境模式 -->
      <div class="sidebar-footer">
        <div class="mode-badge">
          <span class="dot" :class="isMock ? 'mock' : 'live'"></span>
          <span class="mode-text">{{ isMock ? '本地 Mock 桩模式' : 'Agent 实时联调' }}</span>
        </div>
        <div class="version-tag">契约版本: v1.2.0</div>
      </div>
    </aside>

    <!-- 右侧主体内容 -->
    <div class="main-wrapper">
      <!-- 顶部状态栏 -->
      <header class="top-header">
        <div class="breadcrumb">
          <span class="section-badge">{{ currentRouteName }}</span>
        </div>

        <div class="header-right">
          <div class="clock-display">
            <el-icon><Timer /></el-icon>
            <span>{{ currentTime }}</span>
          </div>
          <el-divider direction="vertical" />
          <el-tag type="success" size="small" effect="plain">
            FastAPI API: :8000
          </el-tag>
        </div>
      </header>

      <!-- 页面视图区域 -->
      <main class="page-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  Platform,
  DataBoard,
  Warning,
  Crop,
  ChatDotRound,
  VideoCamera,
  Timer,
} from '@element-plus/icons-vue'
import { isMockEnabled } from '@/api/client'

const route = useRoute()
const isMock = ref(isMockEnabled)

const currentRouteName = computed(() => {
  return (route.meta.title as string) || '控制台'
})

const currentTime = ref('')
let timer: any = null

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleDateString() + ' ' + now.toLocaleTimeString()
}

onMounted(() => {
  updateClock()
  timer = setInterval(updateClock, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.app-layout {
  display: flex;
  width: 100vw;
  height: 100vh;
  background-color: #f8fafc;
  overflow: hidden;
}
.sidebar {
  width: 240px;
  background-color: #0f172a;
  color: #f1f5f9;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 16px;
  border-bottom: 1px solid #1e293b;
}
.brand-icon {
  color: #3b82f6;
}
.brand-text {
  display: flex;
  flex-direction: column;
}
.main-title {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: #f8fafc;
}
.sub-title {
  font-size: 11px;
  color: #94a3b8;
}
.nav-menu {
  flex: 1;
  padding: 16px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 6px;
  color: #94a3b8;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
}
.nav-item:hover {
  background-color: #1e293b;
  color: #f8fafc;
}
.nav-item.active {
  background-color: #2563eb;
  color: #ffffff;
}
.sidebar-footer {
  padding: 16px;
  border-top: 1px solid #1e293b;
  background-color: #0b1120;
}
.mode-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #cbd5e1;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.dot.mock {
  background-color: #eab308;
}
.dot.live {
  background-color: #22c55e;
}
.version-tag {
  font-size: 11px;
  color: #64748b;
  margin-top: 6px;
}
.main-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.top-header {
  height: 56px;
  background-color: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  flex-shrink: 0;
}
.section-badge {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #64748b;
}
.clock-display {
  display: flex;
  align-items: center;
  gap: 6px;
}
.page-content {
  flex: 1;
  overflow: hidden;
  position: relative;
}
</style>
