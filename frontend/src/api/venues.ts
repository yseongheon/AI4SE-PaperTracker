import http from './http'
import type { VenueWithCount } from '../types'

// A 会列表（含各会议论文数），供筛选侧栏与趋势图
export async function listVenues(): Promise<VenueWithCount[]> {
  const { data } = await http.get<VenueWithCount[]>('/venues')
  return data
}
