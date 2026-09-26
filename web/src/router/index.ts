import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
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
  ],
})

router.beforeEach((to, _from, next) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} - 智慧施工安全智能体`
  }
  next()
})

export default router
