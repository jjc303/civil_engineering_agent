<template>
  <div class="copilot-page">
    <ErrorBoundary>
      <header class="header-section">
        <div class="title-area">
          <span class="eyebrow">SAFETY COPILOT</span>
          <h2>{{ uiConfig?.assistant_name || t('copilot.defaultAssistantName') }}</h2>
          <p class="subtitle">{{ t('copilot.subtitle') }}</p>
        </div>
        <router-link to="/learning" class="learning-entry"><el-icon><Document /></el-icon>{{ t('copilot.enterLearning') }}</router-link>
      </header>

      <div class="copilot-layout">
        <div class="chat-container">
          <div class="chat-heading">
            <div><span class="assistant-dot" /><strong>{{ t('copilot.chatTitle') }}</strong><span class="chat-heading-note">{{ t('copilot.chatSubtitle') }}</span></div>
            <span class="session-label">{{ thinking ? t('copilot.sessionThinking') : t('copilot.sessionCurrent') }}</span>
          </div>

          <div ref="scrollRef" class="messages-scroll" role="log" :aria-label="t('copilot.chatLogAria')" :aria-busy="thinking">
            <WelcomePanel v-if="!hasUserMessages" :thinking="thinking" @select-prompt="selectPrompt" />

            <ChatMessage
              v-for="(msg, idx) in visibleMessages"
              :key="idx"
              :msg="msg"
              :thinking="thinking"
              :show-evidence="uiConfig?.show_evidence !== false"
              :assistant-name="uiConfig?.assistant_name || t('copilot.defaultAssistantName')"
              @select-prompt="selectPrompt"
              @view-evidence="viewEvidence"
              @select-guided-target="selectGuidedTarget"
              @confirm-action="confirmAction"
              @cancel-action="cancelAction"
              @open-report-detail="openReportDetail"
              @preview-report-pdf="previewReportPdf"
              @download-report-pdf="downloadReportPdf"
              @open-training-detail="openTrainingDetail"
            />

            <ThinkingIndicator v-if="thinking" :wait-seconds="waitSeconds" :assistant-name="uiConfig?.assistant_name || t('copilot.defaultAssistantName')" />
          </div>

          <div class="quick-prompts">
            <span v-if="quickQuestions.length" class="prompt-hint">{{ t('copilot.quickPromptsLabel') }}</span>
            <button v-for="(q, qIdx) in quickQuestions" :key="qIdx" class="prompt-chip" :disabled="thinking" @click="selectPrompt(q)">{{ q }}</button>
          </div>

          <div class="input-area">
            <el-input
              v-model="inputQuestion"
              :placeholder="uiConfig?.input_placeholder || t('copilot.defaultInputPlaceholder')"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 5 }"
              :aria-label="t('copilot.inputAria')"
              :disabled="thinking"
              @keydown.enter="handleComposerEnter"
            />
            <div class="composer-footer">
              <span>{{ t('copilot.composerHint') }}</span>
              <el-button type="primary" :loading="thinking" :disabled="!inputQuestion.trim() && !thinking" @click="handleSend">
                {{ thinking ? t('copilot.sessionThinking') : t('copilot.sendButton') }} <span v-if="!thinking" aria-hidden="true">↗</span>
              </el-button>
            </div>
          </div>
        </div>

        <CopilotAside />
      </div>

      <EvidenceModal v-model="modalVisible" :record="selectedViolation" />
      <CopilotReportDetailDialog v-model="reportDetailOpen" :report-id="selectedReportId" @preview-pdf="previewReportPdf" />
      <CopilotTrainingDetailDialog v-model="trainingDetailOpen" :training-id="selectedTrainingId" />
      <RectificationCreateDialog v-model="rectificationDialogVisible" :target="selectedRectificationTarget" @proposed="onRectificationProposed" />
      <TrainingSetupDialog v-model="trainingSetupDialogVisible" :target="selectedTrainingReport" @proposed="onTrainingProposed" />
    </ErrorBoundary>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Document } from '@element-plus/icons-vue'
import { downloadReport } from '@/api/learning'
import { useCopilotSession } from '@/composables/useCopilotSession'
import { attachBlobToWindow, triggerBlobDownload } from '@/composables/useObjectUrl'
import { useAppI18n } from '@/i18n/useAppI18n'
import type { ChatMessageItem } from '@/types/chat'
import type { ChatEvidence, GuidedSelectionOption, PendingAction, ViolationRecord } from '@/types/contract'
import ChatMessage from '@/components/ChatMessage.vue'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import EvidenceModal from '@/components/EvidenceModal.vue'
import ThinkingIndicator from '@/components/ThinkingIndicator.vue'
import WelcomePanel from '@/components/WelcomePanel.vue'
import CopilotAside from '@/components/copilot/CopilotAside.vue'
import CopilotReportDetailDialog from '@/components/copilot/CopilotReportDetailDialog.vue'
import CopilotTrainingDetailDialog from '@/components/copilot/CopilotTrainingDetailDialog.vue'
import RectificationCreateDialog from '@/components/copilot/RectificationCreateDialog.vue'
import TrainingSetupDialog from '@/components/copilot/TrainingSetupDialog.vue'

const { t } = useAppI18n()
const scrollRef = ref<HTMLDivElement | null>(null)
const {
  inputQuestion, thinking, waitSeconds, uiConfig, quickQuestions,
  hasUserMessages, visibleMessages, handleSend, selectPrompt,
  appendAssistantMessage, confirmAction, cancelAction,
} = useCopilotSession(scrollRef)

const modalVisible = ref(false), selectedViolation = ref<ViolationRecord | null>(null)
const reportDetailOpen = ref(false), selectedReportId = ref<string | null>(null)
const trainingDetailOpen = ref(false), selectedTrainingId = ref<string | null>(null)
const rectificationDialogVisible = ref(false), selectedRectificationTarget = ref<GuidedSelectionOption | null>(null)
const trainingSetupDialogVisible = ref(false), selectedTrainingReport = ref<GuidedSelectionOption | null>(null)

function handleComposerEnter(event: KeyboardEvent) {
  if (event.shiftKey || event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  void handleSend()
}

function selectGuidedTarget(msg: ChatMessageItem, option: GuidedSelectionOption) {
  if (msg.guidedSelection?.kind === 'CAMERA_TARGET' && option.follow_up_question) {
    return selectPrompt(option.follow_up_question)
  }
  if (msg.guidedSelection?.kind === 'TRAINING_REPORT') {
    selectedTrainingReport.value = option
    trainingSetupDialogVisible.value = true
    return
  }
  selectedRectificationTarget.value = option
  rectificationDialogVisible.value = true
}

const onTrainingProposed = (pending: PendingAction) => appendAssistantMessage({ role: 'assistant', text: t('copilot.trainingPendingCreated'), pendingAction: pending })
const onRectificationProposed = (pending: PendingAction) => appendAssistantMessage({ role: 'assistant', text: t('copilot.rectificationPendingCreated'), pendingAction: pending })

function viewEvidence(ev: ChatEvidence) {
  selectedViolation.value = {
    event_uuid: ev.event_uuid, camera_id: t('copilot.evidenceSnapshotLabel'), monitor_session_id: '-',
    track_id: 0, violation_type: 'NO_HELMET', severity: 'INFO', status: 'ACTIVE', zone_id: null, zone_name: null,
    occurred_at_utc: ev.occurred_at_utc, resolved_at_utc: null, duration_seconds: 0, snapshot_uri: ev.snapshot_uri,
    model_name: null, model_version: null, extra_details: {},
  }
  modalVisible.value = true
}

const openReportDetail = (id: string) => { selectedReportId.value = id; reportDetailOpen.value = true }
const openTrainingDetail = (id: string) => { selectedTrainingId.value = id; trainingDetailOpen.value = true }

async function previewReportPdf(id: string) {
  const tab = window.open('', '_blank')
  if (!tab) return ElMessage.warning(t('copilot.popupBlockedWarning'))
  try {
    attachBlobToWindow(await downloadReport(id), tab)
  } catch {
    tab.close()
    ElMessage.error(t('copilot.pdfPreviewFailed'))
  }
}

async function downloadReportPdf(id: string) {
  try {
    triggerBlobDownload(await downloadReport(id), `safety-report-${id}.pdf`)
  } catch {
    ElMessage.error(t('copilot.pdfDownloadFailed'))
  }
}
</script>

<style scoped>
.copilot-page {
  --el-color-primary: #7563d4; --el-color-primary-light-3: #9b8dde; --el-color-primary-light-5: #bab0ea;
  --el-color-primary-light-7: #d7d0f4; --el-color-primary-light-9: #f2effb; --el-color-primary-dark-2: #6150b5;
  padding: 8px 8px 0; display: flex; flex-direction: column; max-width: 1440px; margin: 0 auto;
  height: 100%; min-height: 0; box-sizing: border-box; color: #39425b;
}
.header-section { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 26px; }
.eyebrow { display: block; color: #9382ca; font-size: 10px; font-weight: 700; letter-spacing: 2px; margin-bottom: 10px; }
.title-area h2 { margin: 0; font-size: 27px; color: #323a50; letter-spacing: -.6px; }
.subtitle { margin: 10px 0 0; font-size: 13px; color: #8590a0; }
.learning-entry { display: inline-flex; align-items: center; gap: 8px; padding: 11px 15px; background: #fff; border: 1px solid #e3ddf5; border-radius: 12px; font-size: 12px; color: #7563bf; text-decoration: none; white-space: nowrap; }
.learning-entry:hover { background: #f1edfb; }
.copilot-layout { display: grid; grid-template-columns: minmax(0, 1fr) 276px; gap: 22px; flex: 1; min-height: 0; }
.chat-container { min-width: 0; min-height: 0; display: flex; flex-direction: column; background: #fff; border: 1px solid #ececf4; border-radius: 20px; overflow: hidden; box-shadow: 0 6px 24px #41336b03; }
.chat-heading { display: flex; justify-content: space-between; gap: 12px; padding: 20px 24px; border-bottom: 1px solid #f0eef6; font-size: 13px; flex-shrink: 0; }
.chat-heading > div { display: flex; gap: 9px; align-items: center; }
.assistant-dot { width: 7px; height: 7px; border-radius: 50%; background: #9481d8; box-shadow: 0 0 0 4px #f1edfb; margin-right: 5px; }
.chat-heading-note, .session-label { font-size: 11px; color: #9a9eaf; }
.chat-heading-note { margin-left: 9px; }
.messages-scroll { flex: 1; min-height: 0; padding: 26px 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 24px; scrollbar-width: thin; scrollbar-color: #ded8ec transparent; }
.quick-prompts { display: flex; align-items: center; gap: 8px; padding: 12px 22px 0; flex-wrap: wrap; flex-shrink: 0; }
.prompt-hint { font-size: 12px; color: #64748b; }
.prompt-chip { font: inherit; font-size: 11px; color: #8b7ca5; background: #faf8fd; border: 1px solid #ece5f5; border-radius: 8px; padding: 7px 9px; cursor: pointer; transition: all .2s; }
.prompt-chip:hover { border-color: #c8b9e5; color: #7861ad; }
.input-area { padding: 14px 22px 18px; background: #fff; flex-shrink: 0; }
.input-area :deep(.el-textarea__inner) { padding: 14px 16px; border-radius: 12px; background: #faf9fc; box-shadow: 0 0 0 1px #e9e3f2 inset; resize: none; font-size: 13px; line-height: 1.7; }
.input-area :deep(.el-textarea__inner:focus) { box-shadow: 0 0 0 1px #a18acd inset; }
.composer-footer { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding-top: 12px; }
.composer-footer > span { font-size: 10px; color: #aaa4b3; }
.composer-footer :deep(.el-button) { border-radius: 10px; font-size: 12px; min-height: 35px; }
.composer-footer :deep(.el-button span) { gap: 12px; }
.copilot-page button:disabled { cursor: default; opacity: .6; }
.copilot-page a:focus-visible, .copilot-page button:focus-visible { outline: 2px solid #9b86d2; outline-offset: 3px; }

@media (max-width: 1180px) { .copilot-layout { grid-template-columns: minmax(0, 1fr) 240px; gap: 16px; } .chat-heading-note { display: none; } }
@media (max-width: 1000px) { .copilot-layout { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 760px) {
  .copilot-page { padding: 4px 0 0; min-height: 520px; } .header-section { margin-bottom: 16px; align-items: flex-start; }
  .title-area { flex: 1; min-width: 0; } .title-area h2 { font-size: 23px; } .subtitle { font-size: 11px; line-height: 1.7; }
  .learning-entry { font-size: 11px; padding: 9px 10px; margin-top: 18px; } .eyebrow { font-size: 9px; margin-bottom: 7px; }
  .chat-heading { padding: 16px; } .messages-scroll { padding: 20px 12px; }
  .quick-prompts { padding: 10px 14px 0; gap: 6px; } .input-area { padding: 12px 14px 14px; } .composer-footer > span { font-size: 9px; }
}
@media (prefers-reduced-motion: reduce) { .prompt-chip { transition: none; } }
</style>
