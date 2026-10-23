import { onBeforeUnmount, watch, watchEffect } from 'vue'
import { useAssistantStore } from '@/stores/assistant'
import type { AssistantPageContext } from '@/api/conversation'
export function useAssistantPage(context: () => AssistantPageContext, refresh?: () => unknown) {
  const assistant = useAssistantStore()
  watchEffect(() => { assistant.pageContext = context() })
  if (refresh) watch(() => assistant.revision, () => { void refresh() })
  onBeforeUnmount(() => { assistant.pageContext = undefined })
  return assistant
}
