<template>
  <ManagedPracticeSession v-if="String(route.params.sessionId).startsWith('L-')" :key="String(route.params.sessionId)" />
  <PracticeSession v-else :key="String(route.params.sessionId)" />
</template>
<script setup lang="ts">
import { useRoute } from 'vue-router'
import ManagedPracticeSession from './ManagedPracticeSession.vue'
import PracticeSession from './PracticeSession.vue'
const route = useRoute()
</script>
