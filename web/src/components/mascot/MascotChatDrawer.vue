<template>
  <Transition name="mascot-drawer">
    <section
      v-if="open"
      class="mascot-drawer"
      :class="[`place-${placement}`, `vertical-${verticalPlacement}`]"
      role="dialog"
      :aria-label="t('mascot.drawerAria', { name: personaName })"
      :style="drawerMaxHeightStyle"
    >
      <header class="drawer-header">
        <div class="drawer-identity">
          <div class="drawer-avatar">
            <MascotAvatarHost
              :state="mascotState"
              :reduced-motion="reducedMotion"
              :speaking-active="speakingActive"
              :size="38"
            />
          </div>
          <div class="drawer-title-group">
            <div class="drawer-title-row">
              <strong>{{ personaName }}</strong>
              <span class="state-pill" :class="`pill-${mascotState}`">{{ stateLabel }}</span>
            </div>
            <small>{{ routeTitle || t('app.workspaceName') }}</small>
          </div>
        </div>

        <div class="drawer-toolbar">
          <button
            v-if="voiceSupported"
            type="button"
            class="icon-btn"
            :class="{ active: voiceEnabled }"
            :title="voiceEnabled ? t('mascot.muteVoice') : t('mascot.enableVoice')"
            :aria-label="voiceEnabled ? t('mascot.muteVoice') : t('mascot.enableVoice')"
            @click="$emit('toggleVoice')"
          >
            <el-icon><Microphone /></el-icon>
          </button>
          <router-link
            to="/copilot"
            class="icon-btn"
            :title="t('mascot.openFullWorkspace')"
            :aria-label="t('mascot.openFullWorkspace')"
            @click="$emit('close')"
          >
            <el-icon><FullScreen /></el-icon>
          </router-link>
          <button
            type="button"
            class="icon-btn"
            :title="t('common.close')"
            :aria-label="t('common.close')"
            @click="$emit('close')"
          >
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </header>

      <div ref="scrollRef" class="drawer-messages" role="log" :aria-busy="thinking">
        <div v-if="!hasUserMessages" class="drawer-welcome">
          <p class="welcome-greeting">{{ contextGreeting }}</p>
          <p class="welcome-sub">{{ uiConfig?.welcome_message || t('copilot.subtitle') }}</p>
        </div>

        <ChatMessage
          v-for="(msg, idx) in visibleMessages"
          :key="idx"
          :msg="msg"
          :thinking="thinking"
          :show-evidence="uiConfig?.show_evidence !== false"
          :assistant-name="personaName"
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

        <div v-if="thinking" class="drawer-thinking">
          <ThinkingIndicator :wait-seconds="waitSeconds" :assistant-name="personaName" />
          <div v-if="stageText" class="stage-chip">{{ stageText }}</div>
        </div>
      </div>

      <div v-if="contextPrompts.length" class="drawer-prompts">
        <button
          v-for="prompt in contextPrompts"
          :key="prompt"
          type="button"
          class="prompt-chip"
          :disabled="thinking"
          @click="selectPrompt(prompt)"
        >
          {{ prompt }}
        </button>
      </div>

      <form class="drawer-composer" @submit.prevent="void handleSend()">
        <el-input
          v-model="inputQuestion"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 3 }"
          :placeholder="uiConfig?.input_placeholder || t('copilot.defaultInputPlaceholder')"
          :aria-label="t('copilot.inputAria')"
          :disabled="thinking"
          @focus="$emit('listening', true)"
          @blur="$emit('listening', false)"
          @keydown.enter="onEnterKey"
        />
        <el-button
          type="primary"
          size="small"
          :loading="thinking"
          :disabled="!inputQuestion.trim() && !thinking"
          @click="void handleSend()"
        >
          {{ t('copilot.sendButton') }}
        </el-button>
      </form>
    </section>
  </Transition>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { Close, FullScreen, Microphone } from '@element-plus/icons-vue'
import ChatMessage from '@/components/ChatMessage.vue'
import ThinkingIndicator from '@/components/ThinkingIndicator.vue'
import MascotAvatarHost from '@/components/mascot/MascotAvatarHost.vue'
import { useCopilotModals } from '@/composables/useCopilotModals'
import { useCopilotSession } from '@/composables/useCopilotSession'
import { useAppI18n } from '@/i18n/useAppI18n'
import { MASCOT_DEFAULTS } from '@/mascot/config'
import type { PageContextPolicy } from '@/mascot/pageContextRegistry'
import type { MascotState } from '@/mascot/stateMachine'
import { useCopilotStore } from '@/stores/copilot'

const props = defineProps<{
  open: boolean
  mascotState: MascotState
  stateLabel: string
  personaName: string
  routeTitle: string
  pagePolicy: PageContextPolicy
  reducedMotion: boolean
  speakingActive: boolean
  voiceEnabled: boolean
  voiceSupported: boolean
  placement: 'left' | 'right'
  verticalPlacement: 'above' | 'below'
  maxHeightPx?: number
}>()

defineEmits<{
  close: []
  toggleVoice: []
  listening: [active: boolean]
}>()

const { t } = useAppI18n()
const scrollRef = ref<HTMLDivElement | null>(null)
const copilotStore = useCopilotStore()
const { thinkingStage, activeToolPurpose } = storeToRefs(copilotStore)

const {
  inputQuestion,
  thinking,
  waitSeconds,
  uiConfig,
  quickQuestions,
  hasUserMessages,
  visibleMessages,
  handleSend,
  selectPrompt,
  confirmAction,
  cancelAction,
} = useCopilotSession(scrollRef)

const {
  viewEvidence,
  openReportDetail,
  openTrainingDetail,
  previewReportPdf,
  downloadReportPdf,
  selectGuidedTarget,
} = useCopilotModals()

const contextGreeting = computed(() => t(props.pagePolicy.greetingKey))
const drawerMaxHeightStyle = computed(() =>
  props.maxHeightPx ? { maxHeight: `${props.maxHeightPx}px` } : undefined,
)

const contextPrompts = computed(() => {
  const fromPolicy = props.pagePolicy.quickPromptKeys.map((key) => t(key))
  if (fromPolicy.length > 0) return fromPolicy
  return quickQuestions.value.slice(0, 3)
})

const stageText = computed(() => {
  if (!thinkingStage.value) return ''
  if (thinkingStage.value === 'executing_tool' && activeToolPurpose.value) {
    return activeToolPurpose.value
  }
  const stageMap: Record<string, string> = {
    retrieving_standards: t('mascot.stages.retrievingStandards'),
    selecting_tool: t('mascot.stages.selectingTool'),
    executing_tool: t('mascot.stages.executingTool'),
    responding: t('mascot.stages.responding'),
  }
  return stageMap[thinkingStage.value] || ''
})

function onEnterKey(event: KeyboardEvent): void {
  if (event.shiftKey || event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  void handleSend()
}
</script>

<style scoped>
.mascot-drawer {
  position: absolute;
  width: min(410px, calc(100vw - 24px));
  max-height: min(620px, 74dvh);
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border: 1px solid #e6e0f5;
  border-radius: 20px;
  box-shadow: 0 20px 50px rgba(38, 30, 74, 0.22);
  overflow: hidden;
  z-index: v-bind('MASCOT_DEFAULTS.zIndexDrawer');
}

.place-left {
  right: 0;
}

.place-right {
  left: 0;
}

.vertical-above {
  bottom: calc(100% + 12px);
}

.vertical-below {
  top: calc(100% + 12px);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  background: linear-gradient(135deg, #f8f6fe, #ffffff);
  border-bottom: 1px solid #f0edf8;
}

.drawer-identity {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.drawer-avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: #efeafd;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.drawer-title-group {
  min-width: 0;
}

.drawer-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.drawer-title-row strong {
  font-size: 14px;
  color: #32394e;
}

.drawer-title-group small {
  display: block;
  font-size: 11px;
  color: #8b92a3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.state-pill {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 999px;
  background: #efecfc;
  color: #6559da;
  font-weight: 600;
}

.pill-alert {
  background: #fee2e2;
  color: #dc2626;
}

.pill-confirm_pending {
  background: #fef3c7;
  color: #b45309;
}

.pill-success {
  background: #d1fae5;
  color: #047857;
}

.pill-error {
  background: #ffedd5;
  color: #c2410c;
}

.drawer-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
}

.icon-btn {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #7c8497;
  text-decoration: none;
}

.icon-btn:hover {
  background: #f1edfc;
  color: #6559da;
}

.icon-btn.active {
  background: #ede9fe;
  color: #6559da;
}

.drawer-messages {
  flex: 1;
  min-height: 180px;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  scrollbar-width: thin;
  scrollbar-color: #dcd5ef transparent;
}

.drawer-welcome {
  padding: 14px;
  border-radius: 14px;
  background: #faf8fe;
  border: 1px dashed #e2daf5;
}

.welcome-greeting {
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 600;
  color: #463d70;
}

.welcome-sub {
  margin: 0;
  font-size: 12px;
  color: #7b8294;
  line-height: 1.6;
}

.drawer-thinking {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stage-chip {
  align-self: flex-start;
  margin-left: 48px;
  padding: 3px 9px;
  border-radius: 999px;
  background: #f3effc;
  color: #6559da;
  font-size: 11px;
}

.drawer-prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 14px 0;
  border-top: 1px solid #f4f1fa;
}

.prompt-chip {
  border: 1px solid #e9e2f6;
  background: #faf8fe;
  color: #6d6191;
  font-size: 11px;
  padding: 5px 9px;
  border-radius: 8px;
}

.prompt-chip:hover:not(:disabled) {
  border-color: #bfb0ea;
  color: #6559da;
}

.drawer-composer {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 10px 14px 12px;
  background: #ffffff;
}

.drawer-composer :deep(.el-textarea__inner) {
  border-radius: 10px;
  background: #faf9fc;
  font-size: 12.5px;
  line-height: 1.5;
  resize: none;
}

.mascot-drawer-enter-active,
.mascot-drawer-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.mascot-drawer-enter-from,
.mascot-drawer-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}
</style>
