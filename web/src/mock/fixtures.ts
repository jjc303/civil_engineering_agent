import type {
  CameraRunConfig,
  CameraStatusResponse,
  ChatResponse,
  ViolationPageResponse,
  ViolationRecord,
  ViolationStatistics,
} from '@/types/contract'

export const mockCameras: CameraStatusResponse[] = [
  {
    camera_id: 'cam-crane-01',
    monitor_session_id: 'sess_20260925_001',
    is_online: true,
    fps: 24.8,
    processed_frame_id: 15420,
    active_workers_count: 2,
    model_name: 'helmet_head_person_m',
    model_version: 'v1.2-yolo',
    reported_at_utc: new Date().toISOString(),
    extra_details: { location: '1号塔吊作业区', resolution: '1920x1080' },
  },
  {
    camera_id: 'cam-gate-02',
    monitor_session_id: 'sess_20260925_002',
    is_online: true,
    fps: 25.0,
    processed_frame_id: 15418,
    active_workers_count: 1,
    model_name: 'helmet_head_person_m',
    model_version: 'v1.2-yolo',
    reported_at_utc: new Date().toISOString(),
    extra_details: { location: '西侧主要人员进出闸口', resolution: '1920x1080' },
  },
  {
    camera_id: 'cam-tower-03',
    monitor_session_id: 'sess_20260925_003',
    is_online: false,
    fps: 0.0,
    processed_frame_id: 8200,
    active_workers_count: 0,
    model_name: 'helmet_head_person_m',
    model_version: 'v1.2-yolo',
    reported_at_utc: new Date(Date.now() - 3600 * 1000).toISOString(),
    extra_details: { location: '基坑开挖深井监测点', resolution: '1920x1080' },
  },
]

export const mockViolations: ViolationRecord[] = [
  {
    event_uuid: 'a5d10bde-ef52-4ef7-8471-50b74c864623',
    camera_id: 'cam-crane-01',
    monitor_session_id: 'sess_20260925_001',
    track_id: 12,
    violation_type: 'DANGER_ZONE_INTRUSION',
    severity: 'CRITICAL',
    status: 'ACTIVE',
    zone_id: 'zone-crane-01',
    zone_name: '塔吊回转作业半径禁行区',
    occurred_at_utc: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
    resolved_at_utc: null,
    duration_seconds: 45.2,
    snapshot_uri: 'snapshots/sample_crane.jpg',
    model_name: 'helmet_head_person_m',
    model_version: 'v1.2-yolo',
    extra_details: {
      dwell_threshold_seconds: 5.0,
      bbox: [450, 320, 580, 680],
      feet_point: [515, 680],
    },
  },
  {
    event_uuid: 'b7e21cfe-ff63-4fa8-9582-61c85d975734',
    camera_id: 'cam-gate-02',
    monitor_session_id: 'sess_20260925_002',
    track_id: 34,
    violation_type: 'NO_HELMET',
    severity: 'WARNING',
    status: 'ACTIVE',
    zone_id: null,
    zone_name: null,
    occurred_at_utc: new Date(Date.now() - 32 * 60 * 1000).toISOString(),
    resolved_at_utc: null,
    duration_seconds: 120.0,
    snapshot_uri: 'snapshots/sample_gate.jpg',
    model_name: 'helmet_head_person_m',
    model_version: 'v1.2-yolo',
    extra_details: {
      bbox: [820, 240, 960, 560],
      feet_point: [890, 560],
    },
  },
  {
    event_uuid: 'c8f32dae-0074-5ab9-a693-72d96ea86845',
    camera_id: 'cam-crane-01',
    monitor_session_id: 'sess_20260925_001',
    track_id: 8,
    violation_type: 'DWELL_TIMEOUT',
    severity: 'WARNING',
    status: 'RESOLVED',
    zone_id: 'zone-crane-01',
    zone_name: '塔吊回转作业半径禁行区',
    occurred_at_utc: new Date(Date.now() - 90 * 60 * 1000).toISOString(),
    resolved_at_utc: new Date(Date.now() - 85 * 60 * 1000).toISOString(),
    duration_seconds: 300.0,
    snapshot_uri: 'snapshots/sample_crane_old.jpg',
    model_name: 'helmet_head_person_m',
    model_version: 'v1.2-yolo',
    extra_details: {
      dwell_threshold_seconds: 30.0,
      bbox: [410, 360, 540, 710],
      feet_point: [475, 710],
    },
  },
]

export const mockPageResponse: ViolationPageResponse = {
  items: mockViolations,
  total: 3,
  limit: 100,
  offset: 0,
}

export const mockStatistics: ViolationStatistics = {
  total_violations: 18,
  average_duration_seconds: 34.6,
  by_type: {
    DANGER_ZONE_INTRUSION: 8,
    NO_HELMET: 7,
    DWELL_TIMEOUT: 3,
  },
  by_severity: {
    CRITICAL: 5,
    WARNING: 10,
    INFO: 3,
  },
}

export const mockCameraZones: Record<string, CameraRunConfig> = {
  'cam-crane-01': {
    camera_id: 'cam-crane-01',
    config_version: 2,
    source_resolution: { width: 1920, height: 1080 },
    enter_debounce_frames: 3,
    exit_debounce_frames: 5,
    helmet_debounce_frames: 5,
    alarm_dwell_threshold_seconds: 5.0,
    zones: [
      {
        zone_id: 'zone-crane-01',
        zone_name: '塔吊回转作业半径禁行区',
        polygon: [
          [350, 200],
          [850, 180],
          [1000, 650],
          [600, 800],
          [280, 550],
        ],
        enabled: true,
        alarm_dwell_threshold_seconds: 5.0,
      },
    ],
  },
}

export const mockChatResponse: ChatResponse = {
  request_id: 'req-' + Math.random().toString(36).substring(2, 10),
  answer:
    '### 今日安全态势诊断结论\n\n经过对 **cam-crane-01** 与 **cam-gate-02** 监测画面的全天分析，今日累计捕获 **18起** 安全违规。\n\n- **最严重隐患**：塔吊回转禁行区在 15 分钟前检测到人员擅自闯入（`CRITICAL`），违规持续已达 45 秒。\n- **通行违规**：西侧进出闸口捕获 7 起未佩戴安全帽行为。\n\n建议现场安全员立即介入核实并制止吊装区作业人员。',
  evidence: [
    {
      event_uuid: 'a5d10bde-ef52-4ef7-8471-50b74c864623',
      occurred_at_utc: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
      snapshot_uri: 'snapshots/sample_crane.jpg',
    },
    {
      event_uuid: 'b7e21cfe-ff63-4fa8-9582-61c85d975734',
      occurred_at_utc: new Date(Date.now() - 32 * 60 * 1000).toISOString(),
      snapshot_uri: 'snapshots/sample_gate.jpg',
    },
  ],
  knowledge_citations: [],
  tool_trace: [
    {
      tool_name: 'get_violation_statistics',
      success: true,
      purpose: '聚合查询全站今日安全违规总数与严重度分布',
      duration_ms: 14,
    },
    {
      tool_name: 'query_violations',
      success: true,
      purpose: '提取 cam-crane-01 最近一起活跃的 CRITICAL 级别闯入事件',
      duration_ms: 22,
    },
  ],
  degraded: false,
}
