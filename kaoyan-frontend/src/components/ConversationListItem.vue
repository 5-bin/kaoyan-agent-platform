<template>
  <div class="conversation-row" :class="{ active }">
    <button class="conversation" :class="{ active }" :title="item.title" :aria-label="item.title" :aria-current="active ? 'true' : undefined" @click="$emit('open', item.id)">{{ item.title }}</button>
    <button class="delete-conversation" :disabled="busy" :title="'删除对话：' + item.title" :aria-label="'删除对话：' + item.title" @click.stop="$emit('delete', item.id)">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7" /></svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import type { Conversation } from '@/api/conversation'
defineProps<{ item: Conversation; active: boolean; busy: boolean }>()
defineEmits<{ open: [id: string]; delete: [id: string] }>()
</script>

<style scoped>
.conversation-row { display:flex; align-items:center; width:100%; min-width:0; flex-shrink:0; border-radius:8px; margin:6px 0 }
.conversation-row:hover,.conversation-row.active { background:var(--c-primary-light) }
.conversation { display:block; box-sizing:border-box; flex:1; min-width:0; height:44px; text-align:left; padding:12px; line-height:20px; border:0; border-radius:8px; background:transparent; color:var(--c-ink); cursor:pointer; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
.delete-conversation { display:flex; align-items:center; justify-content:center; flex:0 0 36px; height:44px; padding:0; border:0; border-radius:8px; background:transparent; color:var(--c-ink-2); cursor:pointer }
.delete-conversation:hover { color:var(--el-color-danger); background:var(--el-color-danger-light-9) }
.delete-conversation:disabled { cursor:wait; opacity:.45 }
button:focus-visible { outline:2px solid var(--el-color-primary); outline-offset:-2px }
</style>
