<template>
  <el-card shadow="never" class="settings-card">
    <template #header>
      <div class="section-card-heading">
        <strong>{{ t('zones.settingsTitle') }}</strong>
        <span>{{ t('zones.settingsHint') }}</span>
      </div>
    </template>

    <div class="zones-panel">
      <div class="zones-toolbar">
        <span class="font-bold">{{ t('zones.dangerZonesCount', { count: zones.length }) }}</span>
        <div>
          <el-button size="small" @click="$emit('duplicateZone')">{{ t('zones.duplicate') }}</el-button>
          <el-button size="small" type="primary" @click="$emit('createZone')">{{ t('zones.addZone') }}</el-button>
        </div>
      </div>
      <div class="zones-list">
        <button
          v-for="(zone, index) in zones"
          :key="zone.zone_id"
          class="zone-list-item"
          :class="{ active: index === selectedZoneIndex }"
          @click="$emit('selectZone', index)"
        >
          <span>{{ zone.zone_name || zone.zone_id }}</span>
          <el-tag size="small" :type="zone.enabled ? 'success' : 'info'">
            {{ zone.enabled ? t('zones.zoneEnabled') : t('zones.zoneDisabled') }}
          </el-tag>
        </button>
      </div>
    </div>

    <el-form label-position="top" :model="rules" class="config-form">
      <el-form-item :label="t('zones.fieldZoneId')">
        <el-input v-model="zoneConfig.zone_id" :placeholder="t('zones.fieldZoneIdPlaceholder')" />
      </el-form-item>

      <el-form-item :label="t('zones.fieldZoneName')">
        <el-input v-model="zoneConfig.zone_name" :placeholder="t('zones.fieldZoneNamePlaceholder')" />
      </el-form-item>

      <el-button size="small" type="danger" plain :disabled="zones.length <= 1" @click="$emit('deleteZone')">
        {{ t('zones.deleteZone') }}
      </el-button>

      <el-form-item :label="t('zones.fieldDwell')">
        <el-input-number v-model="zoneConfig.alarm_dwell_threshold_seconds" :min="0.5" :max="300" :step="0.5" />
      </el-form-item>

      <el-divider />

      <el-form-item :label="t('zones.fieldEnterDebounce')">
        <el-slider v-model="rules.enter_debounce_frames" :min="1" :max="30" show-input />
      </el-form-item>

      <el-form-item :label="t('zones.fieldExitDebounce')">
        <el-slider v-model="rules.exit_debounce_frames" :min="1" :max="30" show-input />
      </el-form-item>

      <el-form-item :label="t('zones.fieldHelmetDebounce')">
        <el-slider v-model="rules.helmet_debounce_frames" :min="1" :max="30" show-input />
      </el-form-item>

      <el-form-item :label="t('zones.fieldEnableFence')">
        <el-switch v-model="zoneConfig.enabled" :active-text="t('zones.switchActiveText')" />
      </el-form-item>

      <div class="polygon-points-preview">
        <div class="preview-title">{{ t('zones.pointsTitle', { count: polygonPoints.length }) }}</div>
        <div class="points-chips">
          <el-tag v-for="(p, idx) in polygonPoints" :key="idx" size="small" closable @close="$emit('removePoint', idx)">
            P{{ idx + 1 }}: [{{ p[0] }}, {{ p[1] }}]
          </el-tag>
        </div>
      </div>

      <div class="submit-section">
        <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" show-icon style="margin-bottom: 12px" />
        <el-button type="primary" size="large" :loading="saving" :disabled="!canSave" style="width: 100%" @click="$emit('save')">
          {{ t('zones.saveAndPublish') }}
        </el-button>
      </div>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import type { ZoneDraftRules } from '@/composables/useZoneDraft'
import { useAppI18n } from '@/i18n/useAppI18n'
import type { DangerZoneConfig } from '@/types/contract'
import type { Point2D } from '@/utils/zoneGeometry'

defineProps<{
  zones: DangerZoneConfig[]
  selectedZoneIndex: number
  zoneConfig: DangerZoneConfig
  rules: ZoneDraftRules
  polygonPoints: Point2D[]
  saveError: string
  saving: boolean
  canSave: boolean
}>()

defineEmits<{
  selectZone: [index: number]
  createZone: []
  duplicateZone: []
  deleteZone: []
  removePoint: [index: number]
  save: []
}>()

const { t } = useAppI18n()
</script>

<style scoped>
.settings-card { min-width: 0; border-radius: 20px; }
.zones-panel { margin-bottom: 16px; border: 1px solid #ebe5f4; border-radius: 12px; background: #faf8fe; padding: 14px; }
.zones-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; font-size: 12px; color: #7f7298; }
.zones-toolbar > div { display: flex; gap: 6px; }
.zones-toolbar .el-button { margin: 0; }
.zones-list { display: flex; flex-direction: column; gap: 6px; max-height: 180px; overflow: auto; }
.zone-list-item { display: flex; align-items: center; justify-content: space-between; width: 100%; border: 1px solid #eee9f5; border-radius: 8px; background: #fff; padding: 10px 11px; text-align: left; cursor: pointer; font-size: 12px; color: #7d7890; gap: 10px; }
.zone-list-item.active { border-color: #c1afe1; background: #f1ebfb; color: #8370ad; }
.polygon-points-preview { margin: 16px 0; border-radius: 12px; background: #f8f5fd; padding: 14px; }
.preview-title { font-size: 11px; color: #9b8ead; margin-bottom: 8px; }
.points-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.settings-card :deep(.el-form-item) { margin-bottom: 22px; }
.settings-card :deep(.el-input-number) { width: 100%; }
.settings-card :deep(.el-slider) { max-width: 100%; }
.submit-section { margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee9f5; }
.submit-section .el-button { font-size: 12px; }

@media (max-width: 1100px) {
  .config-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 24px; }
  .config-form > .el-divider, .polygon-points-preview, .submit-section { grid-column: 1 / -1; }
  .config-form > .el-button { justify-self: start; align-self: start; margin-bottom: 18px; }
}

@media (max-width: 650px) {
  .settings-card { border-radius: 16px; }
  .config-form { display: block; }
}
</style>
