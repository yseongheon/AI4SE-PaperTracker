import http from './http'

export interface HealthInfo {
  status: string
  service: string
  version: string
}

export function getHealth(): Promise<HealthInfo> {
  return http.get<HealthInfo>('/health').then((r) => r.data)
}
