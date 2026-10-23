<template><div class="markdown" v-html="rendered" /></template>
<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
const props = defineProps<{ content: string; allowedUrls?: string[] }>()
const md = new MarkdownIt({ html: false, linkify: false, breaks: true })
md.validateLink = (value: string) => {
  try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password && !!props.allowedUrls?.includes(value) } catch { return false }
}
// Remote images are omitted: drafts must not cause network requests or tracking.
md.renderer.rules.image = () => ''
const defaultLink = md.renderer.rules.link_open || ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))
md.renderer.rules.link_open = (tokens, idx, options, env, self) => { tokens[idx]!.attrSet('target', '_blank'); tokens[idx]!.attrSet('rel', 'noopener noreferrer'); return defaultLink(tokens, idx, options, env, self) }
const rendered = computed(() => DOMPurify.sanitize(md.render(props.content), {
  FORBID_TAGS: ['img', 'iframe', 'style', 'script', 'form'], FORBID_ATTR: ['style']
}))
</script>
<style scoped>
.markdown { overflow-wrap:anywhere; line-height:1.8 }
.markdown :deep(pre) { white-space:pre-wrap; background:var(--c-bg); padding:12px; border-radius:8px }
.markdown :deep(table) { display:block; overflow:auto; border-collapse:collapse }
.markdown :deep(td), .markdown :deep(th) { border:1px solid var(--c-line); padding:6px }
</style>
