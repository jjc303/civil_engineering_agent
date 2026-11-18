import { httpRectificationTasksAdapter } from '../http/rectificationTasks.http'
import type { RectificationTaskFilters, RectificationTasksPort } from '../ports'
import type { RectificationTaskPageResponse } from '@/types/contract'

export const mockRectificationTasksAdapter: RectificationTasksPort = {
  ...httpRectificationTasksAdapter,
  async fetchRectificationTasks(filters: RectificationTaskFilters = {}): Promise<RectificationTaskPageResponse> {
    return {
      items: [],
      total: 0,
      limit: filters.limit || 20,
      offset: filters.offset || 0,
    }
  },
}
