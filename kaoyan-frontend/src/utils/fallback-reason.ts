import type { FallbackReason } from '@/types/api'

/** User-facing text for the fixed AI downgrade codes (2026-11-02 contract). */
const LABELS: Record<FallbackReason, string> = {
  TIMEOUT: '模型响应超时',
  UNAVAILABLE: '模型服务暂不可用',
  BUDGET_EXHAUSTED: '本轮或今日模型调用次数已用完',
  INPUT_TOO_LONG: '内容超出模型输入上限，未发送请求',
  INVALID_OUTPUT: '模型输出格式不符合要求',
  EVIDENCE_MISMATCH: '回答未能与引用资料或记录对齐',
  NUMBER_MISMATCH: '回答中的数字与学习记录不一致',
}

/** Legacy results have no code, and unknown codes are not shown as reasons. */
export function fallbackReasonLabel(reason?: string | null): string {
  return reason && reason in LABELS ? LABELS[reason as FallbackReason] : ''
}
