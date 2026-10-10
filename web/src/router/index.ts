import { shallowRef } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'

export const navigationFailure = shallowRef<{ path: string; title: string } | null>(null)

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/demo',
      redirect: '/dashboard',
    },
    {
      path: '/materials',
      redirect: '/dashboard',
    },
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: () => import('@/views/Dashboard.vue'),
      meta: { title: '安全监控看板' },
    },
    {
      path: '/violations',
      name: 'Violations',
      component: () => import('@/views/Violations.vue'),
      meta: { title: '违规事件中心' },
    },
    {
      path: '/rectification-tasks',
      name: 'RectificationTasks',
      component: () => import('@/views/RectificationTasks.vue'),
      meta: { title: '整改任务中心' },
    },
    {
      path: '/zones',
      name: 'ZoneEditor',
      component: () => import('@/views/ZoneEditor.vue'),
      meta: { title: '危险区域标定' },
    },
    {
      path: '/cameras',
      name: 'CameraManagement',
      component: () => import('@/views/CameraManagement.vue'),
      meta: { title: '摄像头与 CV 节点' },
    },
    {
      path: '/copilot',
      name: 'AgentCopilot',
      component: () => import('@/views/AgentCopilot.vue'),
      meta: { title: '安全智能助手' },
    },
    {
      path: '/learning',
      name: 'LearningCenter',
      component: () => import('@/views/LearningCenter.vue'),
      meta: { title: '学习中心' },
    },
    {
      path: '/learn/:token',
      name: 'WorkerLearning',
      component: () => import('@/views/WorkerLearning.vue'),
      meta: { title: '安全培训' },
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} - 智慧施工安全智能体`
  }
})

// A failed dynamic import can remain rejected in the browser module cache.
// Offer a full document navigation instead of repeating the same cached import.
router.onError((_error, to) => {
  navigationFailure.value = { path: to.fullPath, title: String(to.meta.title || '目标页面') }
})
router.afterEach((_to, _from, failure) => {
  if (!failure) navigationFailure.value = null
})

export default router
