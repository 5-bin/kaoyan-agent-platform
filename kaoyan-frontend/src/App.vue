<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useUserStore } from '@/stores/user'

onMounted(() => {
  const userStore = useUserStore()
  if (userStore.token) void userStore.refreshAvatar()
})
</script>
