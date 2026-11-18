import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as api from '@/api/learning'
import { triggerBlobDownload } from '@/composables/useObjectUrl'
import { useAppI18n, useLocaleRefresh } from '@/i18n/useAppI18n'
import { getLearningTimezone, utcDate, zonedDateBoundaryToIso } from '@/utils/datetime'

export const LEARNING_PAGE_SIZE = 20

export function useLearningCenter() {
  const { t, formatDate, formatDateTime } = useAppI18n()
  const timezone = getLearningTimezone()

  const busy = ref(false)
  const overviewLoading = ref(false)
  const overviewError = ref(false)
  const insightsLoading = ref(false)

  const overview = ref<api.WeeklyOverview | null>(null)
  const insights = ref<api.WeeklyInsights | null>(null)
  const reports = ref<api.Report[]>([])
  const trainings = ref<api.Training[]>([])
  const documents = ref<api.KnowledgeDocument[]>([])
  const allDocuments = ref<api.KnowledgeDocument[]>([])
  const documentTotal = ref(0)
  const documentOffset = ref(0)

  const docQuery = ref('')
  const riskType = ref('')
  const docType = ref<'ACCIDENT_REPORT' | 'STANDARD'>('ACCIDENT_REPORT')
  const documentRange = ref<string[]>([])

  const confirmedReports = computed(() => reports.value.filter((item) => item.status === 'CONFIRMED'))

  const currentInsights = computed(() =>
    insights.value &&
    overview.value &&
    insights.value.period_start_utc === overview.value.period_start_utc &&
    insights.value.risk_codes.join('|') === overview.value.main_risks.map((item) => item.code).join('|')
      ? insights.value
      : null,
  )

  const weeklyTraining = computed(() =>
    (overview.value?.weekly_tasks || [])
      .map((weekly) => {
        const task = trainings.value.find((item) => item.task_id === weekly.task_id)
        return task ? { ...task, weekly } : null
      })
      .filter((item): item is api.Training & { weekly: api.WeeklyOverview['weekly_tasks'][number] } => item !== null),
  )

  const availableRiskTags = computed(() =>
    [
      ...new Set([
        ...documents.value.flatMap((doc) => doc.risk_tags),
        ...allDocuments.value.flatMap((doc) => doc.risk_tags),
        ...(overview.value?.main_risks.map((risk) => risk.label) || []),
      ]),
    ]
      .filter(Boolean)
      .sort(),
  )

  const weekLabel = computed(() =>
    overview.value
      ? `${formatDay(overview.value.period_start_utc)} — ${formatDay(overview.value.period_end_utc)}`
      : t('learning.defaultWeekLabel'),
  )

  function formatDay(value: string): string {
    return formatDate(value, { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' })
  }

  function formatInsightTime(value: string): string {
    return formatDateTime(value, { timeZone: timezone, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  function reportDay(value: string, exclusiveEnd = false): string {
    return formatDate(new Date(utcDate(value).getTime() - (exclusiveEnd ? 1 : 0)), { timeZone: timezone })
  }

  async function runTask(fn: () => Promise<void>): Promise<void> {
    busy.value = true
    try {
      await fn()
    } catch (error) {
      const status = (error as { response?: { status: number } })?.response?.status
      if (!status || status === 404) {
        ElMessage.error(error instanceof Error ? error.message : t('common.operationFailed'))
      }
    } finally {
      busy.value = false
    }
  }

  async function downloadPdf(id: string): Promise<void> {
    triggerBlobDownload(await api.downloadReport(id), `safety-report-${id}.pdf`)
  }

  async function loadOverview(): Promise<void> {
    overviewLoading.value = true
    overviewError.value = false
    try {
      overview.value = await api.getWeeklyOverview()
    } catch {
      overviewError.value = true
    } finally {
      overviewLoading.value = false
    }
  }

  async function loadInsights(force = false): Promise<void> {
    insightsLoading.value = true
    try {
      insights.value = await api.getWeeklyInsights(force)
    } catch {
      if (!insights.value) ElMessage.warning(t('learning.insightsLoadFailed'))
    } finally {
      insightsLoading.value = false
    }
  }

  async function loadDocuments(): Promise<void> {
    const start = documentRange.value?.[0]
    const end = documentRange.value?.[1]
    const dateEnd = end ? zonedDateBoundaryToIso(end, timezone, true) : undefined
    const result = await api.searchDocuments({
      query: docQuery.value || undefined,
      risk_type: riskType.value || undefined,
      document_type: docType.value,
      date_start: start ? zonedDateBoundaryToIso(start, timezone) : undefined,
      date_end: dateEnd,
      offset: documentOffset.value,
    })
    documents.value = result.items
    documentTotal.value = result.total
  }

  async function loadDocumentOptions(query: string, selectedIds: ReadonlyArray<string>): Promise<void> {
    const fetched = (await api.searchDocuments({ query, limit: 100 })).items
    const selected = allDocuments.value.filter((doc) => selectedIds.includes(doc.document_id))
    allDocuments.value = [
      ...selected,
      ...fetched.filter((doc) => !selected.some((item) => item.document_id === doc.document_id)),
    ]
  }

  async function reloadReports(): Promise<void> {
    reports.value = await api.listReports()
  }

  async function reloadTrainings(): Promise<void> {
    trainings.value = await api.listTraining()
  }

  async function refresh(): Promise<void> {
    await Promise.allSettled([
      loadOverview(),
      loadInsights(),
      loadDocuments(),
      reloadReports(),
      reloadTrainings(),
    ])
  }

  useLocaleRefresh(refresh)

  return {
    timezone,
    busy,
    overviewLoading,
    overviewError,
    insightsLoading,
    overview,
    insights,
    reports,
    trainings,
    documents,
    allDocuments,
    documentTotal,
    documentOffset,
    docQuery,
    riskType,
    docType,
    documentRange,
    confirmedReports,
    currentInsights,
    weeklyTraining,
    availableRiskTags,
    weekLabel,
    formatDay,
    formatInsightTime,
    reportDay,
    runTask,
    downloadPdf,
    loadOverview,
    loadInsights,
    loadDocuments,
    loadDocumentOptions,
    reloadReports,
    reloadTrainings,
    refresh,
  }
}
