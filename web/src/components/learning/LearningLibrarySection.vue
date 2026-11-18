<template>
  <section class="surface library-section">
    <div class="section-head">
      <div>
        <span class="section-kicker">{{ t('learning.librarySearchKicker') }}</span>
        <h2>{{ t('learning.libraryTitle') }} <small>· {{ documentTotal }} {{ t('common.unitDocs') }}</small></h2>
      </div>
      <el-button type="primary" plain @click="$emit('openUpload')">{{ t('learning.uploadDocument') }}</el-button>
    </div>

    <div class="filter-row">
      <el-input v-model="queryModel" :placeholder="t('learning.searchLibraryPlaceholder')" clearable @keyup.enter="$emit('filter')" />
      <el-select v-model="docTypeModel" :aria-label="t('learning.docTypeAria')">
        <el-option :label="t('enums.documentType.ACCIDENT_CASE')" value="ACCIDENT_REPORT" />
        <el-option :label="t('enums.documentType.STANDARD')" value="STANDARD" />
      </el-select>
      <el-select v-model="riskTypeModel" :placeholder="t('learning.riskTypePlaceholder')" clearable filterable>
        <el-option v-for="tag in availableRiskTags" :key="tag" :label="tag" :value="tag" />
      </el-select>
      <el-date-picker
        v-model="rangeModel"
        type="daterange"
        value-format="YYYY-MM-DD"
        :range-separator="t('common.rangeSeparator')"
        :start-placeholder="t('common.startDate')"
        :end-placeholder="t('common.endDate')"
        clearable
      />
      <el-button @click="$emit('filter')">{{ t('common.filter') }}</el-button>
    </div>

    <div v-if="documents.length" class="library-grid">
      <button v-for="doc in documents" :key="doc.document_id" class="library-card" @click="$emit('openDocument', doc)">
        <span class="library-type">
          {{ doc.document_type === 'STANDARD' ? t('enums.documentType.STANDARD_MATERIAL') : t('enums.documentType.ACCIDENT_CASE') }}
          <time>{{ doc.document_date ? formatDay(doc.document_date) : t('learning.undatedShort') }}</time>
        </span>
        <strong>{{ doc.title }}</strong>
        <span class="library-summary">{{ doc.summary || t('learning.noSummaryCard') }}</span>
        <span class="library-foot">
          {{ doc.risk_tags.slice(0, 2).join(' · ') || t('learning.untaggedRisk') }}
          <i>{{ t('learning.viewArrow') }}</i>
        </span>
      </button>
    </div>
    <div v-else class="empty-state">
      <strong>{{ t('learning.noMatchedDocs') }}</strong>
      <p>{{ t('learning.noMatchedDocsHint') }}</p>
    </div>

    <el-pagination
      v-if="documentTotal > pageSize"
      class="pagination"
      layout="prev, pager, next"
      :total="documentTotal"
      :page-size="pageSize"
      :current-page="documentOffset / pageSize + 1"
      @current-change="(p: number) => $emit('pageChange', p)"
    />
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { KnowledgeDocument } from '@/api/learning'
import { LEARNING_PAGE_SIZE } from '@/composables/useLearningCenter'
import { useAppI18n } from '@/i18n/useAppI18n'

const props = defineProps<{
  documents: KnowledgeDocument[]
  documentTotal: number
  documentOffset: number
  availableRiskTags: string[]
  docQuery: string
  docType: 'ACCIDENT_REPORT' | 'STANDARD'
  riskType: string
  documentRange: string[]
  formatDay: (value: string) => string
}>()

const emit = defineEmits<{
  'update:docQuery': [val: string]
  'update:docType': [val: 'ACCIDENT_REPORT' | 'STANDARD']
  'update:riskType': [val: string]
  'update:documentRange': [val: string[]]
  filter: []
  pageChange: [page: number]
  openDocument: [doc: KnowledgeDocument]
  openUpload: []
}>()

const { t } = useAppI18n()
const pageSize = LEARNING_PAGE_SIZE

const queryModel = computed({ get: () => props.docQuery, set: (v) => emit('update:docQuery', v) })
const docTypeModel = computed({ get: () => props.docType, set: (v) => emit('update:docType', v) })
const riskTypeModel = computed({ get: () => props.riskType, set: (v) => emit('update:riskType', v) })
const rangeModel = computed({ get: () => props.documentRange, set: (v) => emit('update:documentRange', v) })
</script>

<style scoped>
.surface { border: 1px solid #eceef5; border-radius: 20px; background: #fff; box-shadow: 0 5px 20px #37406607; padding: 24px; }
.section-kicker { color: #7d6bd5; font-size: 10px; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
.section-head h2 { margin: 5px 0 0; font-size: 21px; letter-spacing: -.02em; }
.section-head h2 small { color: #a0a7b4; font-size: 13px; font-weight: 400; }
.filter-row { display: flex; gap: 9px; align-items: center; flex-wrap: wrap; margin-bottom: 18px; }
.filter-row > .el-input { width: 220px; flex: 1; min-width: 170px; }
.filter-row > .el-select { width: 130px; }
.filter-row > .el-date-editor { width: 250px; max-width: 100%; }
.library-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.library-card { width: 100%; border: 1px solid #ebeef4; border-radius: 14px; background: #fff; text-align: left; padding: 18px; display: flex; flex-direction: column; gap: 9px; cursor: pointer; min-height: 166px; transition: box-shadow .2s, transform .2s; }
.library-card:hover { box-shadow: 0 9px 22px #4f4d8d13; transform: translateY(-2px); }
.library-type, .library-foot { font-size: 11px; color: #8b94a4; }
.library-type time { float: right; color: #a9afbb; }
.library-card strong { font-size: 14px; line-height: 1.5; color: #3d465a; }
.library-summary { font-size: 12px; color: #8993a2; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.library-foot { margin-top: auto; }
.library-foot i { float: right; font-style: normal; color: #7665cc; }
.empty-state { padding: 42px 18px; text-align: center; color: #7f8a9d; background: #fafbfe; border-radius: 14px; }
.empty-state strong { display: block; color: #697487; font-size: 14px; }
.empty-state p { font-size: 12px; margin: 8px 0 0; line-height: 1.7; }
.pagination { margin-top: 18px; justify-content: flex-end; }

@media (max-width: 760px) {
  .surface { padding: 18px; border-radius: 16px; }
  .library-grid { grid-template-columns: 1fr; }
  .filter-row > .el-date-editor { width: 100%; }
}
</style>
