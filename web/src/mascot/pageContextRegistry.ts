export type MascotDisplayMode = 'float' | 'dock' | 'hidden'

export type MascotContextKey =
  | 'dashboard'
  | 'violations'
  | 'rectificationTasks'
  | 'zones'
  | 'cameras'
  | 'copilot'
  | 'learning'
  | 'workerLearning'
  | 'default'

export interface PageContextPolicy {
  key: MascotContextKey
  mode: MascotDisplayMode
  greetingKey: string
  quickPromptKeys: readonly string[]
}

const PAGE_CONTEXT_REGISTRY: Readonly<Record<MascotContextKey, PageContextPolicy>> = {
  dashboard: {
    key: 'dashboard',
    mode: 'float',
    greetingKey: 'mascot.context.dashboardGreeting',
    quickPromptKeys: [
      'mascot.prompts.cameraOverview',
      'mascot.prompts.latestViolations',
      'mascot.prompts.todaySummary',
    ],
  },
  violations: {
    key: 'violations',
    mode: 'float',
    greetingKey: 'mascot.context.violationsGreeting',
    quickPromptKeys: [
      'mascot.prompts.latestViolations',
      'mascot.prompts.criticalViolations',
      'mascot.prompts.createRectificationGuide',
    ],
  },
  rectificationTasks: {
    key: 'rectificationTasks',
    mode: 'float',
    greetingKey: 'mascot.context.tasksGreeting',
    quickPromptKeys: [
      'mascot.prompts.createRectificationGuide',
      'mascot.prompts.latestViolations',
      'mascot.prompts.weeklyReport',
    ],
  },
  zones: {
    key: 'zones',
    mode: 'float',
    greetingKey: 'mascot.context.zonesGreeting',
    quickPromptKeys: [
      'mascot.prompts.zoneStandards',
      'mascot.prompts.cameraOverview',
      'mascot.prompts.intrusionStandard',
    ],
  },
  cameras: {
    key: 'cameras',
    mode: 'float',
    greetingKey: 'mascot.context.camerasGreeting',
    quickPromptKeys: [
      'mascot.prompts.cameraOverview',
      'mascot.prompts.workforceSummary',
      'mascot.prompts.latestViolations',
    ],
  },
  copilot: {
    key: 'copilot',
    mode: 'dock',
    greetingKey: 'mascot.context.copilotGreeting',
    quickPromptKeys: [
      'mascot.prompts.cameraOverview',
      'mascot.prompts.weeklyReport',
      'mascot.prompts.trainingTasks',
    ],
  },
  learning: {
    key: 'learning',
    mode: 'float',
    greetingKey: 'mascot.context.learningGreeting',
    quickPromptKeys: [
      'mascot.prompts.weeklyReport',
      'mascot.prompts.trainingTasks',
      'mascot.prompts.standardCatalog',
    ],
  },
  workerLearning: {
    key: 'workerLearning',
    mode: 'hidden',
    greetingKey: 'mascot.context.defaultGreeting',
    quickPromptKeys: [],
  },
  default: {
    key: 'default',
    mode: 'float',
    greetingKey: 'mascot.context.defaultGreeting',
    quickPromptKeys: [
      'mascot.prompts.cameraOverview',
      'mascot.prompts.latestViolations',
      'mascot.prompts.weeklyReport',
    ],
  },
}

export function resolvePageContextPolicy(contextKey?: unknown): PageContextPolicy {
  if (typeof contextKey === 'string' && contextKey in PAGE_CONTEXT_REGISTRY) {
    return PAGE_CONTEXT_REGISTRY[contextKey as MascotContextKey]
  }
  return PAGE_CONTEXT_REGISTRY.default
}
