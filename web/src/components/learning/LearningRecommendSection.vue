<template>
  <section class="surface recommended-section">
    <div class="section-head">
      <div>
        <span class="section-kicker">{{ t('learning.basedOnRisks') }}</span>
        <h2>{{ t('learning.recommendedCasesTitle') }}</h2>
      </div>
      <span class="small-note">{{ t('learning.semanticRetrievalNote') }}</span>
    </div>

    <div v-if="insights?.recommended_cases.length" class="recommend-grid">
      <article v-for="(doc, index) in insights.recommended_cases" :key="doc.document_id" class="recommend-card">
        <div class="recommend-index">{{ String(index + 1).padStart(2, '0') }}</div>
        <div class="recommend-body">
          <div class="card-top">
            <span class="type-pill">{{ t('enums.documentType.ACCIDENT_CASE') }}</span>
            <time>{{ doc.document_date ? formatDay(doc.document_date) : t('learning.undated') }}</time>
          </div>
          <h3>{{ doc.title }}</h3>
          <p class="summary">{{ doc.summary || t('learning.noSummaryHint') }}</p>
          <div class="related">
            <span>{{ t('learning.relatedWeeklyRisks') }}</span>
            <b v-for="risk in doc.related_risks" :key="risk">{{ risk }}</b>
          </div>
          <div class="card-actions">
            <el-button link type="primary" @click="$emit('openDocument', doc)">{{ t('learning.viewDetail') }}</el-button>
            <el-button link @click="$emit('addToTraining', doc)">{{ t('learning.addToTraining') }}</el-button>
          </div>
        </div>
      </article>
    </div>

    <div v-else class="empty-state">
      <strong>{{ loading ? t('learning.searchingCases') : t('learning.noRecommendedCases') }}</strong>
      <p v-if="!loading">
        {{ hasMainRisks ? t('learning.confirmIndexedHint') : t('learning.noRiskFallbackHint') }}
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { KnowledgeDocument, WeeklyInsights } from '@/api/learning'
import { useAppI18n } from '@/i18n/useAppI18n'

defineProps<{
  insights: WeeklyInsights | null
  loading: boolean
  hasMainRisks: boolean
  formatDay: (value: string) => string
}>()

defineEmits<{
  openDocument: [doc: KnowledgeDocument]
  addToTraining: [doc: KnowledgeDocument]
}>()

const { t } = useAppI18n()
</script>

<style scoped>
.surface { border: 1px solid #eceef5; border-radius: 20px; background: #fff; box-shadow: 0 5px 20px #37406607; padding: 24px; }
.section-kicker { color: #7d6bd5; font-size: 10px; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
.section-head h2 { margin: 5px 0 0; font-size: 21px; letter-spacing: -.02em; }
.small-note { color: #919aab; font-size: 12px; }
.recommend-grid { display: grid; gap: 12px; }
.recommend-card { display: flex; gap: 18px; padding: 18px; border: 1px solid #eaeaf4; border-radius: 16px; background: linear-gradient(125deg, #fff, #fbfaff); }
.recommend-index { font: 700 28px Georgia, serif; color: #c7bdec; }
.recommend-body { flex: 1; min-width: 0; }
.card-top, .related, .card-actions { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
.card-top time, .related > span { font-size: 11px; color: #a0a8b5; }
.type-pill { font-size: 10px; background: #eae6fa; color: #725fc8; padding: 4px 8px; border-radius: 5px; }
.recommend-card h3 { margin: 9px 0; font-size: 16px; line-height: 1.5; color: #39425b; }
.summary { font-size: 12px; line-height: 1.8; color: #7e8999; margin: 0 0 11px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.related b { font-size: 10px; font-weight: 500; color: #6b7e9d; background: #edf2fa; padding: 5px 8px; border-radius: 12px; }
.card-actions { margin-top: 12px; }
.empty-state { padding: 42px 18px; text-align: center; color: #7f8a9d; background: #fafbfe; border-radius: 14px; }
.empty-state strong { display: block; color: #697487; font-size: 14px; }
.empty-state p { font-size: 12px; margin: 8px 0 0; line-height: 1.7; }

@media (max-width: 760px) {
  .surface { padding: 18px; border-radius: 16px; }
  .recommend-card { padding: 14px; gap: 10px; }
  .small-note { display: none; }
}
</style>
