import { nextTick, onMounted, watch, type Ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useCopilotStore } from '@/stores/copilot'

/**
 * View-level session facade binding a scrollable container to the shared
 * useCopilotStore singleton so /copilot and the floating IP drawer stay in sync.
 */
export function useCopilotSession(scrollRef: Ref<HTMLDivElement | null>) {
  const store = useCopilotStore()
  const {
    inputQuestion,
    thinking,
    thinkingStage,
    activeToolName,
    activeToolPurpose,
    waitSeconds,
    uiConfig,
    quickQuestions,
    hasUserMessages,
    visibleMessages,
    messageVersion,
  } = storeToRefs(store)

  function scrollToBottom(): void {
    void nextTick(() => {
      if (scrollRef.value) {
        scrollRef.value.scrollTop = scrollRef.value.scrollHeight
      }
    })
  }

  watch([messageVersion, thinking], () => {
    scrollToBottom()
  })

  onMounted(() => {
    store.init()
    if (hasUserMessages.value) {
      scrollToBottom()
    }
  })

  return {
    inputQuestion,
    thinking,
    thinkingStage,
    activeToolName,
    activeToolPurpose,
    waitSeconds,
    uiConfig,
    quickQuestions,
    hasUserMessages,
    visibleMessages,
    handleSend: store.handleSend,
    selectPrompt: store.selectPrompt,
    appendAssistantMessage: store.appendAssistantMessage,
    confirmAction: store.confirmAction,
    cancelAction: store.cancelAction,
    scrollToBottom,
  }
}
