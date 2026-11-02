<template><div class="markdown" v-html="rendered" @click="followInternalLink" /></template>
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { navigationDestinations } from '@/utils/assistant-navigation'
const props = defineProps<{ content: string; allowedUrls?: string[]; navigation?: { target: string }[] }>()
const router = useRouter()
const destinations = computed(() => navigationDestinations.filter(item => props.navigation?.some(value => value.target === item.target)))
const md = new MarkdownIt({ html: false, linkify: false, breaks: true })
md.validateLink = (value: string) => {
  if (destinations.value.some(item => item.path === value)) return true
  try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password && !!props.allowedUrls?.includes(value) } catch { return false }
}
// Link only plain text tokens, never code, existing links, images or draft HTML.
md.core.ruler.after('inline', 'assistant-navigation', state => {
  const aliases = destinations.value.flatMap(item => item.aliases.map(label => ({ label, path: item.path }))).sort((a, b) => b.label.length - a.label.length)
  if (!aliases.length) return
  const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const pattern = new RegExp(aliases.map(item => escape(item.label)).join('|'), 'g')
  for (const block of state.tokens) {
    if (block.type !== 'inline' || !block.children) continue
    let depth = 0
    block.children = block.children.flatMap(token => {
      if (token.type === 'link_open') { depth++; return [token] }
      if (token.type === 'link_close') { depth--; return [token] }
      if (token.type !== 'text' || depth) return [token]
      const parts = []; let start = 0
      for (const match of token.content.matchAll(pattern)) {
        const index = match.index!, item = aliases.find(value => value.label === match[0])!
        if (index > start) { const text = new state.Token('text', '', 0); text.content = token.content.slice(start, index); parts.push(text) }
        const open = new state.Token('link_open', 'a', 1); open.attrSet('href', item.path)
        const text = new state.Token('text', '', 0); text.content = match[0]
        parts.push(open, text, new state.Token('link_close', 'a', -1)); start = index + match[0].length
      }
      if (!start) return [token]
      if (start < token.content.length) { const text = new state.Token('text', '', 0); text.content = token.content.slice(start); parts.push(text) }
      return parts
    })
  }
})
// Remote images are omitted: drafts must not cause network requests or tracking.
md.renderer.rules.image = () => ''
const defaultLink = md.renderer.rules.link_open || ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))
md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const href = tokens[idx]!.attrGet('href')
  if (destinations.value.some(item => item.path === href)) {
    tokens[idx]!.attrSet('data-assistant-route', href!)
  } else {
    tokens[idx]!.attrSet('target', '_blank'); tokens[idx]!.attrSet('rel', 'noopener noreferrer')
  }
  return defaultLink(tokens, idx, options, env, self)
}
function followInternalLink(event: MouseEvent) {
  if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
  const anchor = (event.target as Element)?.closest('a[data-assistant-route]')
  const path = anchor?.getAttribute('href')
  if (path && destinations.value.some(item => item.path === path)) { event.preventDefault(); void router.push(path) }
}
const rendered = computed(() => DOMPurify.sanitize(md.render(props.content), {
  FORBID_TAGS: ['img', 'iframe', 'style', 'script', 'form'], FORBID_ATTR: ['style'], ADD_ATTR: ['target']
}))
</script>
<style scoped>
.markdown { overflow-wrap:anywhere; line-height:1.8 }
.markdown :deep(pre) { white-space:pre-wrap; background:var(--c-bg); padding:12px; border-radius:8px }
.markdown :deep(table) { display:block; overflow:auto; border-collapse:collapse }
.markdown :deep(td), .markdown :deep(th) { border:1px solid var(--c-line); padding:6px }
</style>
