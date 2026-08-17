// 趋势数据聚合：后端按天返回原始计数（DR-020 方案 A），周/月聚合在前端完成
import type { AggregateMode, TrendSeries } from '../types'

export interface Aggregated {
  labels: string[]
  series: TrendSeries[]
}

function parseDate(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d) // 本地时区零点，避免 toISOString 的 UTC 偏移
}

function fmt(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** 返回日期所在周的周一（ISO 周起点） */
export function toMonday(d: Date): Date {
  const day = (d.getDay() + 6) % 7 // getDay(): 0=周日…6=周六 → 0=周一
  const r = new Date(d)
  r.setDate(d.getDate() - day)
  r.setHours(0, 0, 0, 0)
  return r
}

/**
 * 按天序列聚合：
 * - day   原样返回
 * - week  label = 该周周一日期（"2026-06-29"）
 * - month label = "YYYY-MM"
 * 输入 labels 有序（后端保证），聚合后同样有序。
 */
export function aggregateSeries(
  labels: string[],
  series: TrendSeries[],
  mode: AggregateMode,
): Aggregated {
  if (mode === 'day') return { labels, series }
  const keyOf = (s: string) =>
    mode === 'month' ? s.slice(0, 7) : fmt(toMonday(parseDate(s)))

  const buckets = new Map<string, number>()
  const newLabels: string[] = []
  for (const l of labels) {
    const k = keyOf(l)
    if (!buckets.has(k)) {
      buckets.set(k, newLabels.length)
      newLabels.push(k)
    }
  }
  const newSeries = series.map((s) => {
    const values = newLabels.map(() => 0)
    labels.forEach((l, i) => {
      values[buckets.get(keyOf(l))!] += s.values[i]
    })
    return { key: s.key, name: s.name, values }
  })
  return { labels: newLabels, series: newSeries }
}
