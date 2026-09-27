export type ViolationType = "NO_HELMET" | "DANGER_ZONE_INTRUSION" | "DWELL_TIMEOUT";
export type ViolationSeverity = "INFO" | "WARNING" | "CRITICAL";
export type EventStatus = "ACTIVE" | "RESOLVED" | "FALSE_ALARM";

export interface SourceResolution {
  width: number;
  height: number;
}

export interface DangerZoneConfig {
  zone_id: string;
  zone_name: string;
  polygon: [number, number][]; // 顶点 >= 3 个点，每个点为 [x, y] 原始物理像素
  enabled: boolean;
  alarm_dwell_threshold_seconds: number;
}

export interface CameraRunConfig {
  camera_id: string;
  config_version: number;
  source_resolution: SourceResolution;
  enter_debounce_frames: number;
  exit_debounce_frames: number;
  helmet_debounce_frames: number;
  alarm_dwell_threshold_seconds: number;
  zones: DangerZoneConfig[];
}

export interface CameraConfigUpdateRequest {
  expected_version?: number | null;
  source_resolution: SourceResolution;
  enter_debounce_frames: number;
  exit_debounce_frames: number;
  helmet_debounce_frames: number;
  alarm_dwell_threshold_seconds: number;
  zones: DangerZoneConfig[];
}

export interface ViolationRecord {
  event_uuid: string;
  camera_id: string;
  monitor_session_id: string;
  track_id: number;
  violation_type: ViolationType;
  severity: ViolationSeverity;
  status: EventStatus;
  zone_id: string | null;
  zone_name: string | null;
  occurred_at_utc: string; // ISO 8601 UTC
  resolved_at_utc: string | null;
  duration_seconds: number;
  snapshot_uri: string | null;
  model_name: string | null;
  model_version: string | null;
  extra_details: {
    dwell_threshold_seconds?: number;
    bbox?: [number, number, number, number]; // [x1, y1, x2, y2] 绝对像素坐标
    feet_point?: [number, number];          // [x, y] 脚底接地点像素坐标
    [key: string]: any;
  };
}

export interface ViolationPageResponse {
  items: ViolationRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface ViolationStatistics {
  total_violations: number;
  average_duration_seconds: number;
  by_type: Partial<Record<ViolationType, number>>;
  by_severity: Partial<Record<ViolationSeverity, number>>;
}

export interface CameraStatusResponse {
  camera_id: string;
  monitor_session_id: string;
  is_online: boolean;
  fps: number;
  processed_frame_id: number;
  active_workers_count: number;
  model_name: string | null;
  model_version: string | null;
  reported_at_utc: string;
  extra_details: Record<string, any>;
}

export interface ChatEvidence {
  event_uuid: string;
  occurred_at_utc: string;
  snapshot_uri: string | null;
}

export interface KnowledgeCitation {
  document_id: string;
  version_no: number;
  title: string;
  page_or_section: string;
  chunk_id: string;
  relevance_score: number;
}

export interface ToolTraceItem {
  tool_name: "query_violations" | "get_violation_statistics" | "get_camera_status" | "get_all_camera_statuses" | "get_workforce_summary" | "get_current_weather" | "search_knowledge" | "create_rectification_task" | "update_rectification_task" | "start_monitoring" | "stop_monitoring";
  success: boolean;
  purpose: string;
  duration_ms: number;
}

export type PendingActionType = 'create_rectification_task' | 'update_rectification_task' | 'start_monitoring' | 'stop_monitoring';
export type PendingActionStatus = 'PENDING' | 'EXECUTING' | 'EXECUTED' | 'CANCELLED' | 'EXPIRED' | 'FAILED';

export interface PendingAction {
  confirmation_id: string;
  action_type: PendingActionType;
  summary: string;
  expires_at_utc: string;
  status: PendingActionStatus;
}

export interface ActionExecutionResponse {
  confirmation_id: string;
  action_type: PendingActionType;
  status: PendingActionStatus;
  summary: string;
  result: Record<string, any>;
  idempotent: boolean;
}

export interface GuidedSelectionOption {
  option_id: string;
  label: string;
  description: string;
  follow_up_question?: string | null;
}

export interface GuidedSelection {
  kind: 'RECTIFICATION_TARGET' | 'CAMERA_TARGET';
  prompt: string;
  options: GuidedSelectionOption[];
}

export interface ChatRequest {
  question: string;
  conversation_id?: string | null;
}

export interface ChatResponse {
  request_id: string;
  answer: string;
  evidence: ChatEvidence[];
  knowledge_citations: KnowledgeCitation[];
  tool_trace: ToolTraceItem[];
  pending_action?: PendingAction | null;
  guided_selection?: GuidedSelection | null;
  degraded: boolean;
  error_code?: string | null;
}

export interface AssistantUiConfig {
  version: number;
  assistant_name: string;
  welcome_message: string;
  input_placeholder: string;
  quick_questions: string[];
  show_evidence: boolean;
  updated_at_utc: string;
}

export interface ApiErrorResponse {
  detail: string | Array<{ loc: (string | number)[]; msg: string; type: string }>;
}

export interface CvNodeResponse {
  node_id: string;
  display_name: string;
  control_url: string;
  is_online: boolean;
  active_sessions: number;
  capacity: number;
  last_heartbeat_at_utc: string | null;
}

export interface ManagedCameraResponse {
  camera_id: string;
  display_name: string;
  node_id: string;
  source_type: 'rtsp' | 'file';
  source_uri_masked: string;
  desired_state: 'RUNNING' | 'STOPPED';
  monitor_session_id: string | null;
}

export type RectificationTaskStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';

export interface RectificationTaskRecord {
  task_id: string;
  event_uuid: string;
  title: string;
  description: string | null;
  owner: string;
  due_at_utc: string;
  status: RectificationTaskStatus;
  completed_at_utc: string | null;
  created_at_utc: string;
  updated_at_utc: string;
  camera_id: string;
  violation_type: ViolationType;
  severity: ViolationSeverity;
  violation_status: EventStatus;
  occurred_at_utc: string;
  snapshot_uri: string | null;
}

export interface RectificationTaskAudit {
  audit_id: string;
  task_id: string;
  action: string;
  actor: string;
  detail_safe_json: Record<string, unknown>;
  created_at_utc: string;
}

export interface RectificationTaskDetail {
  task: RectificationTaskRecord;
  violation: ViolationRecord;
  audits: RectificationTaskAudit[];
}

export interface RectificationTaskPageResponse {
  items: RectificationTaskRecord[];
  total: number;
  limit: number;
  offset: number;
}
