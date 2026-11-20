import { shallowRef } from 'vue'
import { createRouter, createWebHistory, type RouteLocationNormalizedLoaded } from 'vue-router'
import { translateAppMessage } from '@/i18n'

export const navigationFailure = shallowRef<{ path: string; titleKey: string } | null>(null)

export function resolveRouteTitle(route: Pick<RouteLocationNormalizedLoaded, 'meta'>): string {
  const titleKey = typeof route.meta?.titleKey === 'string' ? route.meta.titleKey : ''
  return titleKey ? translateAppMessage(titleKey) : ''
}

export function syncDocumentTitle(route: Pick<RouteLocationNormalizedLoaded, 'meta'>): void {
  const pageTitle = resolveRouteTitle(route)
  if (pageTitle) {
    document.title = `${pageTitle} - ${translateAppMessage('app.titleSuffix')}`
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
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
      meta: { titleKey: 'route.dashboard', layout: 'monitor', ipContextKey: 'dashboard' },
    },
    {
      path: '/violations',
      name: 'Violations',
      component: () => import('@/views/Violations.vue'),
      meta: { titleKey: 'route.violations', layout: 'business', ipContextKey: 'violations' },
    },
    {
      path: '/rectification-tasks',
      name: 'RectificationTasks',
      component: () => import('@/views/RectificationTasks.vue'),
      meta: { titleKey: 'route.rectificationTasks', layout: 'business', ipContextKey: 'rectificationTasks' },
    },
    {
      path: '/zones',
      name: 'ZoneEditor',
      component: () => import('@/views/ZoneEditor.vue'),
      meta: { titleKey: 'route.zones', layout: 'business', ipContextKey: 'zones' },
    },
    {
      path: '/cameras',
      name: 'CameraManagement',
      component: () => import('@/views/CameraManagement.vue'),
      meta: { titleKey: 'route.cameras', layout: 'business', ipContextKey: 'cameras' },
    },
    {
      path: '/copilot',
      name: 'AgentCopilot',
      component: () => import('@/views/AgentCopilot.vue'),
      meta: { titleKey: 'route.copilot', layout: 'business', ipContextKey: 'copilot' },
    },
    {
      path: '/learning',
      name: 'LearningCenter',
      component: () => import('@/views/LearningCenter.vue'),
      meta: { titleKey: 'route.learning', layout: 'business', ipContextKey: 'learning' },
    },
    {
      path: '/learn/:token',
      name: 'WorkerLearning',
      component: () => import('@/views/WorkerLearning.vue'),
      meta: { titleKey: 'route.workerLearning', layout: 'standalone', ipContextKey: 'workerLearning' },
    },
  ],
})

router.beforeEach((to) => {
  syncDocumentTitle(to)
})

// A failed dynamic import can remain rejected in the browser module cache.
// Offer a full document navigation instead of repeating the same cached import.
router.onError((_error, to) => {
  navigationFailure.value = {
    path: to.fullPath,
    titleKey: typeof to.meta.titleKey === 'string' ? to.meta.titleKey : 'app.fallbackPageTitle',
  }
})
router.afterEach((_to, _from, failure) => {
  if (!failure) navigationFailure.value = null
})

export default router
