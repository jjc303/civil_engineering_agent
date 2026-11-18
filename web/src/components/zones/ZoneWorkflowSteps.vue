<template>
  <section class="zone-workflow" :aria-label="t('zones.workflowAria')">
    <div>
      <b>01</b>
      <span>
        <strong>{{ t('zones.step1Title') }}</strong>
        <small>{{ cameraId || t('zones.step1Empty') }}</small>
      </span>
    </div>
    <div>
      <b>02</b>
      <span>
        <strong>{{ t('zones.step2Title') }}</strong>
        <small>{{ t('zones.step2Points', { count: pointCount }) }}</small>
      </span>
    </div>
    <div :class="{ unsaved: dirty }">
      <b>03</b>
      <span>
        <strong>{{ t('zones.step3Title') }}</strong>
        <small>
          {{ dirty ? t('zones.step3Unsaved') : version > 0 ? t('zones.step3Loaded', { version }) : t('zones.step3Waiting') }}
        </small>
      </span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useAppI18n } from '@/i18n/useAppI18n'

defineProps<{
  cameraId: string
  pointCount: number
  version: number
  dirty: boolean
}>()

const { t } = useAppI18n()
</script>

<style scoped>
.zone-workflow {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  padding: 22px 24px;
  margin-bottom: 24px;
  background: #fff;
  border: 1px solid #ece9f4;
  border-radius: 18px;
}

.zone-workflow > div {
  display: flex;
  gap: 12px;
  align-items: center;
  min-width: 0;
}

.zone-workflow b {
  font-size: 12px;
  font-weight: 500;
  color: #9d87c6;
  background: #f5f0fc;
  border-radius: 10px;
  padding: 10px;
}

.zone-workflow strong {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #61617c;
}

.zone-workflow small {
  display: block;
  font-size: 10px;
  margin-top: 7px;
  color: #a0a0b0;
  overflow-wrap: anywhere;
}

.zone-workflow .unsaved small {
  color: #b18960;
}

@media (max-width: 650px) {
  .zone-workflow {
    padding: 17px 12px;
    gap: 8px;
    border-radius: 14px;
  }

  .zone-workflow > div {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .zone-workflow strong {
    font-size: 11px;
  }

  .zone-workflow small {
    font-size: 10px;
    line-height: 1.7;
  }

  .zone-workflow b {
    padding: 7px 8px;
  }
}
</style>
