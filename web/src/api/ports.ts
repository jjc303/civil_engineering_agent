import type {
  ActionExecutionResponse,
  AssistantUiConfig,
  CameraConfigUpdateRequest,
  CameraRunConfig,
  CameraStatusResponse,
  ChatRequest,
  ChatResponse,
  CvNodeResponse,
  EventStatus,
  ManagedCameraResponse,
  PendingAction,
  RectificationTaskDetail,
  RectificationTaskPageResponse,
  RectificationTaskRecord,
  RectificationTaskStatus,
  ViolationPageResponse,
  ViolationRecord,
  ViolationSeverity,
  ViolationStatistics,
  ViolationType,
} from '@/types/contract'

export interface ApiNotifier {
  error(message: string): void
  warning(message: string): void
}

export type ApiTranslator = (key: string, params?: Record<string, string | number>) => string

const noopNotifier: ApiNotifier = {
  error: () => undefined,
  warning: () => undefined,
}

const fallbackTranslator: ApiTranslator = (key, params) => {
  if (!params) return key
  const summary = Object.entries(params)
    .map(([k, v]) => `${k}=${String(v)}`)
    .join(', ')
  return `${key} (${summary})`
}

let activeNotifier: ApiNotifier = noopNotifier
let activeTranslator: ApiTranslator = fallbackTranslator

export function registerApiNotifier(notifier: ApiNotifier): void {
  activeNotifier = notifier
}

export function resetApiNotifier(): void {
  activeNotifier = noopNotifier
}

export function getApiNotifier(): ApiNotifier {
  return activeNotifier
}

export function registerApiTranslator(translator: ApiTranslator): void {
  activeTranslator = translator
}

export function resetApiTranslator(): void {
  activeTranslator = fallbackTranslator
}

export function translateApiMessage(
  key: string,
  params?: Record<string, string | number>,
): string {
  return activeTranslator(key, params)
}

// --- Domain API Query & Payload Contracts ---

export interface ViolationQueryParams {
  camera_id?: string
  violation_type?: ViolationType
  severity?: ViolationSeverity
  status?: EventStatus
  start_time_utc?: string
  end_time_utc?: string
  limit?: number
  offset?: number
}

export interface RiskHeatmapData {
  lookback_days: number
  total_violations: number
  daily_counts: number[]
  hourly_risk: Array<{ hour: number; count: number; risk_level: string; risk_pct: number }>
  zone_risks: Array<{ zone_name: string; camera_id: string; total: number; by_type: Record<string, number>; risk_score: number }>
  summary: string
}

export interface CvNodeMediaEntry {
  name: string
  path: string
}

export interface CvNodeMediaDirectory {
  current_path: string
  parent_path: string | null
  directories: CvNodeMediaEntry[]
  files: CvNodeMediaEntry[]
}

export interface RectificationTaskFilters {
  status?: RectificationTaskStatus
  owner?: string
  overdue?: boolean
  limit?: number
  offset?: number
}

export interface CreateRectificationTaskPayload {
  conversation_id: string
  event_uuid: string
  title: string
  description?: string
  owner: string
  due_at_utc: string
}

export interface UpdateRectificationTaskPayload {
  conversation_id: string
  owner?: string
  due_at_utc?: string
  status?: RectificationTaskStatus
  note?: string
}

export type RealtimeConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'closed' | 'disabled'

export interface RealtimeViolationEventPayload {
  operation: 'CREATED' | 'UPDATED' | string
  record: ViolationRecord
}

export interface SafetyEventStreamCallbacks {
  onStateChange?: (state: RealtimeConnectionState) => void
  onViolationEvent?: (payload: RealtimeViolationEventPayload) => void
  onCameraStatus?: (status: CameraStatusResponse) => void
}

export interface SafetyEventStreamHandle {
  close: () => void
}

export interface CamerasPort {
  fetchCameras(): Promise<CameraStatusResponse[]>
  fetchCameraStatus(cameraId: string): Promise<CameraStatusResponse>
}

export interface ViolationsPort {
  fetchViolations(params?: ViolationQueryParams): Promise<ViolationPageResponse>
  fetchViolationStatistics(params?: {
    camera_id?: string
    start_time_utc?: string
    end_time_utc?: string
  }): Promise<ViolationStatistics>
  fetchRiskHeatmap(lookbackDays?: number): Promise<RiskHeatmapData>
}

export interface ZonesPort {
  fetchCameraZones(cameraId: string): Promise<CameraRunConfig | null>
  updateCameraZones(cameraId: string, request: CameraConfigUpdateRequest): Promise<CameraRunConfig>
}

export interface ChatPort {
  sendChatMessage(request: ChatRequest): Promise<ChatResponse>
  proposeTrainingAction(
    conversationId: string,
    training: {
      report_id: string
      title: string
      document_ids: string[]
      target_count: number
      question_count: number
      pass_score: number
    },
  ): Promise<PendingAction>
  confirmPendingAction(confirmationId: string, conversationId: string): Promise<ActionExecutionResponse>
  cancelPendingAction(confirmationId: string, conversationId: string): Promise<ActionExecutionResponse>
}

export interface CameraManagementPort {
  fetchCvNodes(): Promise<CvNodeResponse[]>
  createCvNode(payload: {
    node_id: string
    display_name: string
    control_url: string
    capacity: number
  }): Promise<CvNodeResponse & { control_token: string }>
  fetchManagedCameras(): Promise<ManagedCameraResponse[]>
  createManagedCamera(payload: {
    camera_id: string
    display_name: string
    node_id: string
    source_type: 'rtsp' | 'file'
    source_uri: string
  }): Promise<ManagedCameraResponse>
  updateManagedCamera(
    cameraId: string,
    payload: {
      display_name?: string
      node_id: string
      source_type: 'rtsp' | 'file'
      source_uri?: string
    },
  ): Promise<ManagedCameraResponse>
  fetchNodeMediaFiles(nodeId: string, directory?: string): Promise<CvNodeMediaDirectory>
  setMonitoring(cameraId: string, action: 'start' | 'stop'): Promise<void>
}

export interface RectificationTasksPort {
  fetchRectificationTasks(filters?: RectificationTaskFilters): Promise<RectificationTaskPageResponse>
  fetchRectificationTask(taskId: string): Promise<RectificationTaskDetail>
  createRectificationTask(payload: CreateRectificationTaskPayload): Promise<RectificationTaskRecord>
  updateRectificationTask(taskId: string, payload: UpdateRectificationTaskPayload): Promise<RectificationTaskRecord>
  proposeRectificationTaskCreate(payload: CreateRectificationTaskPayload): Promise<PendingAction>
  proposeRectificationTaskUpdate(taskId: string, payload: UpdateRectificationTaskPayload): Promise<PendingAction>
}

export interface UiConfigPort {
  fetchAssistantUiConfig(): Promise<AssistantUiConfig>
}

export interface RealtimePort {
  createSafetyEventStream(callbacks: SafetyEventStreamCallbacks): SafetyEventStreamHandle
}
