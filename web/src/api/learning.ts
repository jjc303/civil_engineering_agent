import { apiClient } from './client'

const base = '/api/v1/learning'

export interface Citation { document_id: string; title: string; page_or_section: string; chunk_id: string; document_type: string }
export interface ReportContent { summary: string; risk_analysis: string; remediation: string }
export interface Report { report_id: string; period_start_utc: string; period_end_utc: string; status: string; statistics: { total: number; by_type: Record<string, number>; by_severity: Record<string, number>; by_zone: Record<string, number>; repeat_occurrences: number }; citations: Citation[]; content: ReportContent; pdf_url: string | null; created_at_utc: string }
export interface KnowledgeDocument { document_id: string; title: string; source_label: string; source_display: string; document_type: 'STANDARD' | 'ACCIDENT_REPORT'; validity_status: string; document_date: string | null; risk_tags: string[]; summary: string | null; status: string; relevance_score?: number | null }
export interface CaseDetail { document_id: string; title: string; process: string; causes: string; risks: string; prevention: string; citations: Citation[] }
export interface Question { stem: string; options: string[]; answer: number; evidence?: string | null }
export interface Training { task_id: string; report_id: string; status: string; title: string; target_count: number; question_count: number; pass_score: number; selected_documents: Array<{ document_id: string; title: string; document_type: string; version_no: number; validity_status: string }>; material: string; questions: Question[]; public_url: string | null; qr_url: string | null }
export interface TrainingStatistics { target_count: number; completed_count: number; completion_rate: number; average_score: number; pass_rate: number; submissions: Array<{ worker_id: string; worker_name: string; score: number; passed: boolean; submitted_at_utc: string }> }
export interface WeeklyOverview { period_start_utc: string; period_end_utc: string; total_events: number; high_risk_events: number; training_count: number; completed_count: number; target_count: number; completion_rate: number; main_risks: Array<{ code: string; label: string; count: number }>; weekly_tasks: Array<{ task_id: string; status: string; completed_count: number; target_count: number; average_score: number }> }
export interface WeeklyInsights { period_start_utc: string; risk_codes: string[]; recommended_cases: Array<KnowledgeDocument & { related_risks: string[]; relevance_score: number }>; advice: string; generated_at_utc: string }

export const getWeeklyOverview = async () => (await apiClient.get<WeeklyOverview>(`${base}/overview`)).data
export const getWeeklyInsights = async (refresh = false) => (await apiClient.get<WeeklyInsights>(`${base}/overview/insights`, { params: { refresh }, timeout: 120000 })).data
export const listReports = async () => (await apiClient.get<Report[]>(`${base}/reports`)).data
export const getReport = async (id: string) => (await apiClient.get<Report>(`${base}/reports/${id}`)).data
export const createReport = async (period_start_utc: string, period_end_utc: string) => (await apiClient.post<Report>(`${base}/reports`, { period_start_utc, period_end_utc }, { timeout: 120000 })).data
export const editReport = async (id: string, content: ReportContent) => (await apiClient.put<Report>(`${base}/reports/${id}`, content)).data
export const deleteReport = async (id: string) => { await apiClient.delete(`${base}/reports/${id}`) }
export const confirmReport = async (id: string) => (await apiClient.post<Report>(`${base}/reports/${id}:confirm`, {}, { timeout: 120000 })).data
export const downloadReport = async (id: string) => (await apiClient.get<Blob>(`${base}/reports/${id}/pdf`, { responseType: 'blob' })).data
export const searchDocuments = async (params: { query?: string; risk_type?: string; document_type?: string; date_start?: string; date_end?: string; offset?: number; limit?: number }) => (await apiClient.get<{ items: KnowledgeDocument[]; total: number }>(`${base}/documents`, { params })).data
export const getCaseDetail = async (id: string) => (await apiClient.get<CaseDetail>(`${base}/documents/${id}/case-detail`, { timeout: 120000 })).data
export const getDocumentFragments = async (id: string) => (await apiClient.get<{ items: Array<{ content: string; citation: Citation }> }>(`${base}/documents/${id}/fragments`)).data
export const uploadDocument = async (file: File, fields: { title: string; source_label: string; document_type: string; document_date: string; risk_tags: string; summary: string }) => {
  const data = new FormData(); data.append('file', file)
  Object.entries(fields).forEach(([key, value]) => { if (value) data.append(key, key === 'document_date' ? `${value}T00:00:00+08:00` : value) })
  return (await apiClient.post('/api/v1/knowledge/documents', data, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 })).data
}
export const updateDocumentMetadata = async (id: string, payload: { document_date: string | null; risk_tags: string[]; summary: string | null; source_display: string | null }) => (await apiClient.patch(`/api/v1/knowledge/documents/${id}/metadata`, payload)).data
export const regenerateDocumentSummary = async (id: string) => (await apiClient.post<KnowledgeDocument>(`/api/v1/knowledge/documents/${id}:summarize`, {}, { timeout: 120000 })).data
export const updateStandardValidity = async (id: string, validity_status: string) => (await apiClient.patch(`/api/v1/knowledge/documents/${id}/validity`, { validity_status })).data
export const retireDocument = async (id: string) => apiClient.post(`/api/v1/knowledge/documents/${id}:retire`, {})
export const listTraining = async () => (await apiClient.get<Training[]>(`${base}/training`)).data
export const getTraining = async (id: string) => (await apiClient.get<Training>(`${base}/training/${id}`)).data
export const createTraining = async (payload: { report_id: string; title: string; document_ids: string[]; target_count: number; question_count: number; pass_score: number }) => (await apiClient.post<Training>(`${base}/training`, payload, { timeout: 120000 })).data
export const editTraining = async (id: string, payload: { title: string; target_count: number; pass_score: number; material: string; questions: Question[] }) => (await apiClient.put<Training>(`${base}/training/${id}`, payload)).data
export const deleteTraining = async (id: string) => { await apiClient.delete(`${base}/training/${id}`) }
export const publishTraining = async (id: string) => (await apiClient.post<Training>(`${base}/training/${id}:publish`, {})).data
export const getTrainingStats = async (id: string) => (await apiClient.get<TrainingStatistics>(`${base}/training/${id}/statistics`)).data
export const getTrainingQr = async (id: string) => (await apiClient.get<Blob>(`${base}/training/${id}/qr`, { responseType: 'blob' })).data
export const getPublicTraining = async (token: string) => (await apiClient.get<{ title: string; material: string; questions: Array<{ stem: string; options: string[] }> }>(`/api/v1/learn/${token}`)).data
export const submitTraining = async (token: string, payload: { worker_id: string; worker_name: string; answers: number[] }) => (await apiClient.post<{ score: number; passed: boolean }>(`/api/v1/learn/${token}/submissions`, payload)).data
