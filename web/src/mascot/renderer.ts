import type { MascotState } from './stateMachine'

export type MascotRendererId = 'svg' | 'rive'

export interface MascotGazeOffset {
  x: number
  y: number
}

export interface MascotRenderProps {
  state: MascotState
  gazeOffset: MascotGazeOffset
  reducedMotion: boolean
  hasPendingAction: boolean
  unreadAlerts: number
  speakingActive: boolean
  size: number
}

export interface MascotRendererDescriptor {
  id: MascotRendererId
  displayName: string
}

export const DEFAULT_MASCOT_RENDERER: MascotRendererId = 'svg'

export const MASCOT_RENDERERS: Readonly<Record<MascotRendererId, MascotRendererDescriptor>> = {
  svg: { id: 'svg', displayName: 'Vector SVG Safety Mascot' },
  rive: { id: 'rive', displayName: 'Rive State-Machine Adapter (Extensible)' },
}
