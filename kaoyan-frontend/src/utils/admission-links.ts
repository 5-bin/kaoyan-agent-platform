import sources from '../../../config/admission-sources.json'
import type { AdmissionLinks, LegacyAdmissionCheck } from '@/types/api'

interface Source {
  code: string
  name: string
  hosts: string[]
  entries: string[]
  year: number
}

const registry = new Map<string, Source>(
  (sources as Source[]).map(source => [source.code, source]),
)

export const ADMISSION_CONFIRM_TEXT = '请自行确认招生年份、专业及报考条件。'
export const ADMISSION_YEAR_NOTE = '登记年份不代表当前内容年份或最新招生年度。'
export const ADMISSION_SAFE_ANSWER = '已展示登记招生官网链接。' + ADMISSION_CONFIRM_TEXT
export const ADMISSION_LEGACY_NO_LINK = '该院校未在登记清单中，无法展示招生官网链接。请以院校官方渠道自行确认。'
export const ADMISSION_LINK_UNVERIFIED = '招生官网链接未通过登记校验，已隐藏。'

function project(source: Source): AdmissionLinks {
  return {
    schoolCode: source.code,
    schoolName: source.name,
    registeredYear: source.year,
    entryUrls: [...source.entries],
  }
}

/** Derive links from the trusted registry, never from an old record's URLs or evidence. */
export function linksForCode(code?: string): AdmissionLinks | undefined {
  const source = code ? registry.get(code) : undefined
  return source ? project(source) : undefined
}

/** Verify a new result against the same exact registry before it reaches the page. */
export function projectLinks(value?: AdmissionLinks): AdmissionLinks | undefined {
  if (!value) return undefined
  const source = registry.get(value.schoolCode)
  if (!source || value.schoolName !== source.name || value.registeredYear !== source.year) return undefined
  if (!Array.isArray(value.entryUrls) || value.entryUrls.length !== source.entries.length) return undefined
  if (value.entryUrls.some((url, index) => url !== source.entries[index])) return undefined
  return project(source)
}

/** Legacy checks expose only a school code; arbitrary old URLs are intentionally ignored. */
export function legacyLinks(check?: LegacyAdmissionCheck): AdmissionLinks | undefined {
  return linksForCode(check?.query?.schoolCode)
}

/** Require exact registry membership plus safe HTTPS before rendering an anchor. */
export function safeRegisteredUrl(links: AdmissionLinks, value: string): string | undefined {
  const source = registry.get(links.schoolCode)
  if (!source || !source.entries.includes(value)) return undefined
  try {
    const url = new URL(value)
    if (url.protocol !== 'https:' || url.username || url.password || url.hash) return undefined
    if (url.port && url.port !== '443') return undefined
    if (!source.hosts.includes(url.hostname)) return undefined
    return url.href
  } catch {
    return undefined
  }
}

/** The registry-scope answer may link only exact, safe URLs already registered locally. */
export function registeredAdmissionUrls(): string[] {
  return [...registry.values()].flatMap(source => {
    const links = project(source)
    return source.entries.filter(url => Boolean(safeRegisteredUrl(links, url)))
  })
}
