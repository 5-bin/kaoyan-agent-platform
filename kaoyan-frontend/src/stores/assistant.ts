import { defineStore } from 'pinia'
import type { AssistantPageContext } from '@/api/conversation'
export const useAssistantStore = defineStore('assistant', {
  state: () => ({ conversationId: '', open: false, pageContext: undefined as AssistantPageContext | undefined, revision: 0, selectedNoteId: '', noteRevision: 0 }),
  actions: {
    reset() { this.conversationId = ''; this.open = false; this.pageContext = undefined; this.revision = 0; this.selectedNoteId = ''; this.noteRevision = 0 },
    selectNote(id: string) { this.selectedNoteId = id; this.noteRevision++; this.open = true },
    notesChanged() { this.noteRevision++ },
    changed() { this.revision++ }
  }
})
