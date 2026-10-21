export function historyNotice(status?: string): string {
  switch (status) {
    case 'NOT_ANSWERED': return '尚无有效作答，提交后可查看答案与解析。'
    case 'PARTIAL': return '历史快照不完整，仅展示当时保存的内容。'
    case 'MISSING': return '历史题目快照缺失，无法展示当时的答案与解析。'
    case 'UNAVAILABLE': return '题目或判分已不可用，暂不展示答案与解析。'
    default: return ''
  }
}
