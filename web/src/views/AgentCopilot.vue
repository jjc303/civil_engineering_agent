<template>
  <div class="copilot-page">
    <div class="header-section">
      <div class="title-area">
        <h2>{{ uiConfig?.assistant_name || '智能助手' }}</h2>
      </div>
      <el-tag type="success" effect="plain">
        <el-icon><Cpu /></el-icon> 事实依据驱动 · 防幻觉架构
      </el-tag>
    </div>

    <!-- 问答主体区 -->
    <div class="chat-container">
      <!-- 消息列表 -->
      <div class="messages-scroll" ref="scrollRef">
        <div v-for="(msg, idx) in messages" :key="idx" :class="['message-row', msg.role]">
          <!-- 头像 -->
          <div class="avatar">
            <el-avatar :icon="msg.role === 'user' ? UserFilled : Service" :size="36" />
          </div>

          <!-- 消息内容 -->
          <div class="message-content">
            <div class="sender-name">{{ msg.role === 'user' ? '用户' : (uiConfig?.assistant_name || '智能助手') }}</div>

            <!-- 用户气泡 -->
            <div v-if="msg.role === 'user'" class="user-bubble">
              {{ msg.text }}
            </div>

            <!-- 智能体回答气泡 -->
            <div v-else class="agent-bubble">
              <!-- 降级提醒 -->
              <el-alert
                v-if="msg.degraded"
                title="服务处于降级保护模式，以下回答来自本地规则或缓存数据"
                type="warning"
                show-icon
                :closable="false"
                style="margin-bottom: 12px"
              />

              <!-- Markdown 渲染的主回答 -->
              <div class="markdown-body" v-html="renderMarkdown(msg.text)"></div>

              <!-- 证据卡片区 -->
              <div v-if="uiConfig?.show_evidence && msg.evidence && msg.evidence.length > 0" class="evidence-section">
                <div class="evidence-header">
                  <el-icon><Picture /></el-icon>
                  <span>关联证据快照 ({{ msg.evidence.length }} 项):</span>
                </div>
                <div class="evidence-grid">
                  <div
                    v-for="(ev, eIdx) in msg.evidence"
                    :key="eIdx"
                    class="evidence-card"
                    @click="viewEvidence(ev)"
                  >
                    <img :src="resolveMediaUrl(ev.snapshot_uri)" class="thumb-img" alt="证据快照" />
                    <div class="evidence-info">
                      <span class="ev-time">{{ formatTime(ev.occurred_at_utc) }}</span>
                      <span class="ev-uuid font-mono">{{ ev.event_uuid.substring(0, 8) }}...</span>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="msg.knowledgeCitations && msg.knowledgeCitations.length > 0" class="evidence-section">
                <div class="evidence-header"><el-icon><Document /></el-icon><span>知识资料引用 ({{ msg.knowledgeCitations.length }} 项):</span></div>
                <div v-for="citation in msg.knowledgeCitations" :key="citation.chunk_id" class="tool-item">
                  <span>{{ citation.title }}（v{{ citation.version_no }}，{{ citation.page_or_section }}）</span>
                  <el-tag size="small" type="info">相关度 {{ citation.relevance_score.toFixed(2) }}</el-tag>
                </div>
              </div>

              <!-- 智能体执行链路 (Tool Trace) -->
              <div v-if="msg.toolTrace && msg.toolTrace.length > 0" class="trace-section">
                <el-collapse>
                  <el-collapse-item name="trace">
                    <template #title>
                      <div class="trace-title">
                        <el-icon><Operation /></el-icon>
                        <span>智能体工具调用轨迹 ({{ msg.toolTrace.length }} 次调用，已审计)</span>
                      </div>
                    </template>
                    <el-timeline style="padding-left: 8px; margin-top: 8px">
                      <el-timeline-item
                        v-for="(t, tIdx) in msg.toolTrace"
                        :key="tIdx"
                        :type="t.success ? 'primary' : 'danger'"
                        size="small"
                      >
                        <div class="tool-item">
                          <span class="tool-name font-mono">{{ t.tool_name }}</span>
                          <span class="tool-purpose">{{ t.purpose }}</span>
                          <el-tag size="small" type="info">{{ t.duration_ms }} ms</el-tag>
                        </div>
                      </el-timeline-item>
                    </el-timeline>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>
          </div>
        </div>

        <!-- 思考中指示器 -->
        <div v-if="thinking" class="message-row assistant">
          <div class="avatar">
            <el-avatar :icon="Service" :size="36" />
          </div>
          <div class="message-content">
            <div class="sender-name">{{ uiConfig?.assistant_name || '智能助手' }}</div>
            <div class="agent-bubble thinking-bubble">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>正在分析施工安全数据与调用工具中...</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 快捷提问推荐 -->
      <div class="quick-prompts">
        <span v-if="quickQuestions.length" class="prompt-hint">快捷提问：</span>
        <el-tag
          v-for="(q, qIdx) in quickQuestions"
          :key="qIdx"
          class="prompt-chip"
          effect="plain"
          @click="selectPrompt(q)"
        >
          {{ q }}
        </el-tag>
      </div>

      <!-- 输入框 -->
      <div class="input-area">
        <el-input
          v-model="inputQuestion"
          :placeholder="uiConfig?.input_placeholder || '请输入问题'"
          size="large"
          clearable
          :disabled="thinking"
          @keyup.enter="handleSend"
        >
          <template #append>
            <el-button type="primary" :loading="thinking" @click="handleSend">
              发送提问
            </el-button>
          </template>
        </el-input>
      </div>
    </div>

    <!-- 证据弹窗 -->
    <EvidenceModal v-model="modalVisible" :record="selectedViolation" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick, onMounted } from 'vue'
import {
  UserFilled,
  Service,
  Picture,
  Document,
  Operation,
  Loading,
  Cpu,
} from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import { sendChatMessage } from '@/api/chat'
import { fetchAssistantUiConfig } from '@/api/uiConfig'
import { resolveMediaUrl } from '@/api/client'
import type { AssistantUiConfig, ChatEvidence, ToolTraceItem, ViolationRecord } from '@/types/contract'
import EvidenceModal from '@/components/EvidenceModal.vue'

interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  evidence?: ChatEvidence[]
  knowledgeCitations?: import('@/types/contract').KnowledgeCitation[]
  toolTrace?: ToolTraceItem[]
  degraded?: boolean
}

const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
})

const scrollRef = ref<HTMLDivElement | null>(null)
const inputQuestion = ref('')
const thinking = ref(false)

const modalVisible = ref(false)
const selectedViolation = ref<ViolationRecord | null>(null)

const uiConfig = ref<AssistantUiConfig | null>(null)
const quickQuestions = ref<string[]>([])

const messages = reactive<ChatMessage[]>([])

const chatHistoryKey = 'agent_chat_messages'

function renderMarkdown(content: string): string {
  return md.render(content || '')
}

function selectPrompt(q: string) {
  inputQuestion.value = q
  handleSend()
}

async function handleSend() {
  const q = inputQuestion.value.trim()
  if (!q || thinking.value) return

  messages.push({ role: 'user', text: q })
  saveMessages()
  inputQuestion.value = ''
  thinking.value = true
  scrollToBottom()

  try {
    const res = await sendChatMessage({
      question: q,
      conversation_id: getConversationId(),
    })

    messages.push({
      role: 'assistant',
      text: res.answer,
      evidence: res.evidence,
      knowledgeCitations: res.knowledge_citations,
      toolTrace: res.tool_trace,
      degraded: res.degraded,
    })
    saveMessages()
  } catch (err: any) {
    messages.push({
      role: 'assistant',
      text: `请求未能正常完成: ${err.message || '网络连接超时'}`,
      degraded: true,
    })
    saveMessages()
  } finally {
    thinking.value = false
    scrollToBottom()
  }
}

function getConversationId(): string {
  const key = 'agent_conversation_id'
  const existing = sessionStorage.getItem(key)
  if (existing) return existing
  const created = crypto.randomUUID()
  sessionStorage.setItem(key, created)
  return created
}

function saveMessages() {
  // Browser-session display history is intentionally separate from the
  // server-side 24-hour summarized context and never leaves this tab.
  sessionStorage.setItem(chatHistoryKey, JSON.stringify(messages))
}

function restoreMessages() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(chatHistoryKey) || '[]')
    if (Array.isArray(saved) && saved.length > 0) {
      messages.splice(0, messages.length, ...saved)
    }
  } catch {
    sessionStorage.removeItem(chatHistoryKey)
  }
}

function viewEvidence(ev: ChatEvidence) {
  selectedViolation.value = ev as unknown as ViolationRecord
  modalVisible.value = true
}

function formatTime(utcStr: string): string {
  if (!utcStr) return '-'
  return new Date(utcStr).toLocaleTimeString()
}

function scrollToBottom() {
  nextTick(() => {
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight
    }
  })
}

onMounted(() => {
  getConversationId()
  restoreMessages()
  fetchAssistantUiConfig().then((config) => {
    uiConfig.value = config
    quickQuestions.value = config.quick_questions
    if (!messages.length) messages.push({ role: 'assistant', text: config.welcome_message })
  }).catch(() => undefined)
  scrollToBottom()
})
</script>

<style scoped>
.copilot-page {
  padding: 24px;
  display: flex;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;
}
.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.title-area h2 {
  margin: 0;
  font-size: 22px;
  color: #0f172a;
}
.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: #64748b;
}
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}
.messages-scroll {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.message-row {
  display: flex;
  gap: 12px;
  max-width: 85%;
}
.message-row.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}
.message-row.assistant {
  align-self: flex-start;
}
.sender-name {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 4px;
}
.message-row.user .sender-name {
  text-align: right;
}
.user-bubble {
  background: #2563eb;
  color: #ffffff;
  padding: 12px 16px;
  border-radius: 12px 2px 12px 12px;
  font-size: 14px;
  line-height: 1.5;
}
.agent-bubble {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #1e293b;
  padding: 16px;
  border-radius: 2px 12px 12px 12px;
  font-size: 14px;
  line-height: 1.6;
}
.thinking-bubble {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
}
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin-top: 10px;
  margin-bottom: 6px;
  color: #0f172a;
}
.markdown-body :deep(p) {
  margin: 6px 0;
}
.markdown-body :deep(ul) {
  padding-left: 20px;
  margin: 6px 0;
}
.evidence-section {
  margin-top: 14px;
  border-top: 1px dashed #e2e8f0;
  padding-top: 10px;
}
.evidence-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 8px;
}
.evidence-grid {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.evidence-card {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.evidence-card:hover {
  border-color: #2563eb;
  transform: translateY(-2px);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}
.thumb-img {
  width: 50px;
  height: 50px;
  object-fit: cover;
  border-radius: 4px;
  background: #0f172a;
}
.evidence-info {
  display: flex;
  flex-direction: column;
  font-size: 11px;
}
.ev-time {
  color: #64748b;
}
.ev-uuid {
  color: #2563eb;
}
.trace-section {
  margin-top: 12px;
}
.trace-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #64748b;
}
.tool-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.tool-name {
  font-weight: 600;
  color: #0f172a;
}
.tool-purpose {
  color: #64748b;
}
.font-mono {
  font-family: ui-monospace, monospace;
}
.quick-prompts {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #f8fafc;
  border-top: 1px solid #f1f5f9;
}
.prompt-hint {
  font-size: 12px;
  color: #64748b;
}
.prompt-chip {
  cursor: pointer;
  transition: all 0.2s;
}
.prompt-chip:hover {
  border-color: #2563eb;
  color: #2563eb;
}
.input-area {
  padding: 16px;
  background: #ffffff;
  border-top: 1px solid #e2e8f0;
}
</style>
