import type {
  ChatEvidence,
  GuidedSelection,
  KnowledgeCitation,
  PendingAction,
  ReportPreview,
  ToolTraceItem,
  TrainingPreview,
} from './contract'

export interface ChatMessageItem {
  role: 'user' | 'assistant'
  text: string
  evidence?: ChatEvidence[]
  knowledgeCitations?: KnowledgeCitation[]
  reportPreviews?: ReportPreview[]
  reportCount?: number
  trainingPreviews?: TrainingPreview[]
  trainingCount?: number
  toolTrace?: ToolTraceItem[]
  degraded?: boolean
  errorCode?: string | null
  retryQuestion?: string
  pendingAction?: PendingAction
  guidedSelection?: GuidedSelection
  actionBusy?: boolean
  actionResult?: string
  actionReportId?: string
  actionReportPdf?: boolean
  actionTrainingId?: string
  actionTrainingUrl?: string
}
