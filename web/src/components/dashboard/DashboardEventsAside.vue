<template>
  <aside class="event-column">
    <section class="events-panel">
      <div class="section-heading">
        <div>
          <h2>{{ t('dashboard.attentionTitle') }} <span class="event-total">{{ eventLoaded ? eventTotal : '—' }}</span></h2>
          <p>{{ t('dashboard.attentionDesc') }}</p>
        </div>
        <router-link class="quiet-link" to="/violations">{{ t('dashboard.viewAll') }}</router-link>
      </div>
      <div v-if="!eventLoaded || !events.length" class="section-empty compact">
        <el-icon><CircleCheck v-if="eventLoaded" /><Warning v-else /></el-icon>
        <h3>{{ eventLoaded ? t('dashboard.noActiveViolations') : loading ? t('dashboard.readingEvents') : t('dashboard.eventsUnavailable') }}</h3>
        <p>{{ eventLoaded ? t('dashboard.noActiveEventsDesc') : t('dashboard.eventsUnavailableDesc') }}</p>
      </div>
      <div v-else class="event-list">
        <button
          v-for="(event, index) in events"
          :key="event.event_uuid"
          class="event-item"
          :class="{ critical: event.severity === 'CRITICAL', featured: index === 0 }"
          @click="$emit('openEvidence', event)"
        >
          <span class="event-rank">{{ String(index + 1).padStart(2, '0') }}</span>
          <div class="event-body">
            <div class="event-topline">
              <b>{{ violationLabel(event.violation_type) }}</b>
              <span class="severity-tag" :class="event.severity.toLowerCase()">{{ severityLabel(event.severity) }}</span>
            </div>
            <span class="event-location">{{ event.camera_id }}</span>
            <div class="event-bottomline">
              <time>{{ formatEventTime(event.occurred_at_utc, true) }}</time>
              <span>{{ t('dashboard.viewEvidence') }}</span>
            </div>
            <p v-if="index === 0" class="event-detail">
              {{ t('dashboard.durationSeconds', { seconds: event.duration_seconds.toFixed(1) }) }}
              <span v-if="event.zone_name"> · {{ event.zone_name }}</span>
            </p>
          </div>
        </button>
      </div>
      <div class="events-footer">
        {{ eventsSourceTime }}
        <span v-if="eventTotal > events.length">{{ t('dashboard.showingRecent', { count: events.length }) }}</span>
      </div>
    </section>
    <router-link to="/copilot" class="assistant-card">
      <div class="assistant-icon"><el-icon><ChatDotRound /></el-icon></div>
      <div>
        <h3>{{ t('dashboard.copilotTitle') }}</h3>
        <p>{{ t('dashboard.copilotDesc') }}</p>
        <span>{{ t('dashboard.copilotAsk') }} <i>↗</i></span>
      </div>
    </router-link>
  </aside>
</template>

<script setup lang="ts">
import { ChatDotRound, CircleCheck, Warning } from '@element-plus/icons-vue'
import { useAppI18n } from '@/i18n/useAppI18n'
import type { ViolationRecord, ViolationSeverity, ViolationType } from '@/types/contract'

defineProps<{
  eventLoaded: boolean
  events: ViolationRecord[]
  eventTotal: number
  loading: boolean
  eventsSourceTime: string
  violationLabel: (type: ViolationType) => string
  severityLabel: (severity: ViolationSeverity) => string
  formatEventTime: (value: string | Date, date?: boolean) => string
}>()

defineEmits<{
  openEvidence: [event: ViolationRecord]
}>()

const { t } = useAppI18n()
</script>

<style scoped>
.event-column {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.events-panel {
  padding: 22px 20px;
  background: #fff;
  border: 1px solid #ece9f4;
  border-radius: 20px;
}

.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding-bottom: 12px;
  margin: 0;
}

.section-heading h2 {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  color: #4a526b;
}

.section-heading p {
  font-size: 11px;
  line-height: 1.7;
  color: #9c99ad;
  margin: 7px 0 0;
}

.event-total {
  font-size: 10px;
  font-weight: 400;
  background: #f1edff;
  color: #8a78ce;
  padding: 3px 7px;
  margin-left: 8px;
  border-radius: 9px;
}

.quiet-link {
  font-size: 10px;
  color: #8a7bcc;
  text-decoration: none;
}

.section-empty.compact {
  min-height: 220px;
  border: 0;
  padding: 25px 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #a09ab9;
}

.section-empty.compact > .el-icon {
  width: 58px;
  height: 58px;
  border-radius: 50%;
  background: #eef6f0;
  color: #90b39a;
  font-size: 28px;
}

.section-empty.compact h3 {
  font-size: 14px;
  font-weight: 400;
  color: #74798c;
  margin: 18px 0 8px;
}

.section-empty.compact p {
  font-size: 12px;
  color: #858c9d;
  margin: 0;
  line-height: 1.9;
}

.event-item {
  width: 100%;
  text-align: left;
  display: flex;
  align-items: flex-start;
  padding: 19px 8px;
  gap: 12px;
  border: 0;
  border-bottom: 1px solid #f0f1f6;
  border-radius: 8px;
  color: #646b7b;
  background: none;
  transition: background 0.2s, transform 0.2s;
}

.event-item:hover {
  background: #f7f5fe;
  transform: translateX(2px);
}

.event-item.featured {
  background: linear-gradient(90deg, #f7f2fe, transparent);
}

.event-rank {
  font-size: 10px;
  color: #788b98;
  padding-top: 3px;
}

.critical .event-rank {
  color: #cb9384;
}

.event-body {
  flex: 1;
  min-width: 0;
}

.event-topline {
  display: flex;
  justify-content: space-between;
  gap: 6px;
  align-items: center;
}

.event-topline b {
  font-size: 12px;
  font-weight: 500;
  color: #626076;
}

.severity-tag {
  font-size: 9px;
  padding: 2px 5px;
  border-radius: 3px;
  white-space: nowrap;
}

.severity-tag.critical {
  background: #b56a571c;
  color: #c46957;
}

.severity-tag.warning {
  background: #b3996017;
  color: #a77d36;
}

.severity-tag.info {
  background: #67839820;
  color: #718ca5;
}

.event-location {
  display: block;
  color: #8297a5;
  font-size: 11px;
  margin-top: 9px;
  overflow-wrap: anywhere;
}

.event-bottomline {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
  font-size: 11px;
  color: #7d929f;
}

.event-bottomline > span {
  color: #7969d0;
}

.event-detail {
  font-size: 10px;
  line-height: 1.8;
  color: #9fa8ac;
  margin: 12px 0 0;
}

.events-footer {
  font-size: 9px;
  color: #81889a;
  margin: 15px 0 0;
}

.assistant-card {
  display: flex;
  gap: 13px;
  padding: 24px 22px;
  margin-top: 25px;
  border: 0;
  border-radius: 18px;
  background: linear-gradient(148deg, #6355be, #8c77d8);
  text-decoration: none;
  transition: transform 0.2s, box-shadow 0.2s;
}

.assistant-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 24px #7e6cca14;
}

.assistant-icon {
  color: #eee8ff;
  font-size: 22px;
}

.assistant-card > div:last-child {
  flex: 1;
}

.assistant-card h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  color: #fff;
}

.assistant-card p {
  color: #e1dbf5;
  font-size: 11px;
  margin: 9px 0 19px;
}

.assistant-card span {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #fff;
  border-top: 1px solid #ffffff28;
  padding-top: 12px;
}

.assistant-card i {
  font-style: normal;
}

@media (max-width: 1100px) {
  .event-column {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 260px;
    gap: 20px;
  }

  .assistant-card {
    margin-top: 0;
    align-self: start;
  }
}

@media (max-width: 760px) {
  .event-column {
    grid-template-columns: minmax(0, 1fr);
  }

  .events-panel {
    border-radius: 16px;
  }
}
</style>
