<template>
  <section class="metrics" :aria-label="t('dashboard.metricsAria')">
    <div>
      <p>{{ t('dashboard.metricCamerasOnline') }} <small>{{ t('dashboard.metricCamerasHint') }}</small></p>
      <strong>{{ cameraLoaded ? onlineCount : '—' }}<em>/ {{ cameraLoaded ? totalCameras : '—' }}</em></strong>
      <span :class="{ stale: camerasStale }">{{ cameraSourceTime }}</span>
    </div>
    <div>
      <p>{{ t('dashboard.metricTodayViolations') }} <small>{{ dayLabel }}</small></p>
      <strong>{{ stats?.total_violations ?? '—' }}<em>{{ t('common.unitCount') }}</em></strong>
      <span :class="{ stale: statsStale }">{{ statsSourceTime }}</span>
    </div>
    <div>
      <p>{{ t('dashboard.metricTodayCritical') }} <small>{{ t('dashboard.metricCriticalHint') }}</small></p>
      <strong class="critical-number">{{ stats ? stats.by_severity.CRITICAL ?? 0 : '—' }}<em>{{ t('common.unitCount') }}</em></strong>
      <span :class="{ stale: statsStale }">{{ statsSourceTime }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useAppI18n } from '@/i18n/useAppI18n'
import type { ViolationStatistics } from '@/types/contract'

defineProps<{
  cameraLoaded: boolean
  onlineCount: number
  totalCameras: number
  camerasStale: boolean
  cameraSourceTime: string
  stats: ViolationStatistics | null
  dayLabel: string
  statsStale: boolean
  statsSourceTime: string
}>()

const { t } = useAppI18n()
</script>

<style scoped>
.metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
  margin-bottom: 24px;
}

.metrics > div {
  border: 1px solid #ece9f4;
  border-radius: 18px;
  background: #fff;
  padding: 22px 24px;
  box-shadow: 0 3px 16px #28356103;
}

.metrics p {
  margin: 0 0 11px;
  font-size: 12px;
  color: #8590a2;
}

.metrics p small {
  display: inline;
  margin-left: 8px;
  font-size: 10px;
  color: #a1a3b3;
}

.metrics strong {
  font-size: 32px;
  line-height: 1.3;
  font-weight: 600;
  color: #645383;
  letter-spacing: -0.8px;
  font-variant-numeric: tabular-nums;
}

.metrics strong em {
  font-size: 13px;
  color: #a1a6b3;
  font-weight: 400;
  font-style: normal;
  letter-spacing: 0;
  margin-left: 10px;
}

.metrics strong.critical-number {
  color: #ce7666;
}

.metrics > div > span {
  display: block;
  color: #a19eaf;
  font-size: 10px;
  margin-top: 8px;
}

.metrics .stale {
  color: #ce7666;
}

@media (max-width: 760px) {
  .metrics {
    gap: 9px;
  }

  .metrics > div {
    padding: 17px 12px;
    border-radius: 14px;
  }

  .metrics p {
    font-size: 11px;
  }

  .metrics strong {
    font-size: 27px;
  }

  .metrics strong em {
    font-size: 11px;
    margin-left: 4px;
  }

  .metrics > div > span {
    font-size: 9px;
  }
}

@media (max-width: 620px) {
  .metrics p small {
    display: none;
  }
}
</style>
