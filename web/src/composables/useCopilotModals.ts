import { reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadReport } from '@/api/learning'
import { attachBlobToWindow, triggerBlobDownload } from '@/composables/useObjectUrl'
import { translateAppMessage } from '@/i18n'
import { useCopilotStore } from '@/stores/copilot'
import type { ChatMessageItem } from '@/types/chat'
import type {
  ChatEvidence,
  GuidedSelectionOption,
  PendingAction,
  ViolationRecord,
} from '@/types/contract'

const modalState = reactive({
  evidenceVisible: false,
  selectedViolation: null as ViolationRecord | null,
  reportDetailOpen: false,
  selectedReportId: null as string | null,
  trainingDetailOpen: false,
  selectedTrainingId: null as string | null,
  rectificationDialogVisible: false,
  selectedRectificationTarget: null as GuidedSelectionOption | null,
  trainingSetupDialogVisible: false,
  selectedTrainingReport: null as GuidedSelectionOption | null,
})

/**
 * Shared modal & evidence orchestration used by both AgentCopilot.vue
 * and the floating IP drawer (via CopilotGlobalModals.vue).
 */
export function useCopilotModals() {
  const copilotStore = useCopilotStore()

  function openViolationRecord(record: ViolationRecord): void {
    modalState.selectedViolation = record
    modalState.evidenceVisible = true
  }

  function viewEvidence(ev: ChatEvidence): void {
    openViolationRecord({
      event_uuid: ev.event_uuid,
      camera_id: translateAppMessage('copilot.evidenceSnapshotLabel'),
      monitor_session_id: '-',
      track_id: 0,
      violation_type: 'NO_HELMET',
      severity: 'INFO',
      status: 'ACTIVE',
      zone_id: null,
      zone_name: null,
      occurred_at_utc: ev.occurred_at_utc,
      resolved_at_utc: null,
      duration_seconds: 0,
      snapshot_uri: ev.snapshot_uri,
      model_name: null,
      model_version: null,
      extra_details: {},
    })
  }

  function openReportDetail(id: string): void {
    modalState.selectedReportId = id
    modalState.reportDetailOpen = true
  }

  function openTrainingDetail(id: string): void {
    modalState.selectedTrainingId = id
    modalState.trainingDetailOpen = true
  }

  async function previewReportPdf(id: string): Promise<void> {
    const tab = window.open('', '_blank')
    if (!tab) {
      ElMessage.warning(translateAppMessage('copilot.popupBlockedWarning'))
      return
    }
    try {
      attachBlobToWindow(await downloadReport(id), tab)
    } catch {
      tab.close()
      ElMessage.error(translateAppMessage('copilot.pdfPreviewFailed'))
    }
  }

  async function downloadReportPdf(id: string): Promise<void> {
    try {
      triggerBlobDownload(await downloadReport(id), `safety-report-${id}.pdf`)
    } catch {
      ElMessage.error(translateAppMessage('copilot.pdfDownloadFailed'))
    }
  }

  function selectGuidedTarget(msg: ChatMessageItem, option: GuidedSelectionOption): void {
    if (msg.guidedSelection?.kind === 'CAMERA_TARGET' && option.follow_up_question) {
      copilotStore.selectPrompt(option.follow_up_question)
      return
    }
    if (msg.guidedSelection?.kind === 'TRAINING_REPORT') {
      modalState.selectedTrainingReport = option
      modalState.trainingSetupDialogVisible = true
      return
    }
    modalState.selectedRectificationTarget = option
    modalState.rectificationDialogVisible = true
  }

  function onTrainingProposed(pending: PendingAction): void {
    copilotStore.appendAssistantMessage({
      role: 'assistant',
      text: translateAppMessage('copilot.trainingPendingCreated'),
      pendingAction: pending,
    })
  }

  function onRectificationProposed(pending: PendingAction): void {
    copilotStore.appendAssistantMessage({
      role: 'assistant',
      text: translateAppMessage('copilot.rectificationPendingCreated'),
      pendingAction: pending,
    })
  }

  return {
    modalState,
    openViolationRecord,
    viewEvidence,
    openReportDetail,
    openTrainingDetail,
    previewReportPdf,
    downloadReportPdf,
    selectGuidedTarget,
    onTrainingProposed,
    onRectificationProposed,
  }
}
