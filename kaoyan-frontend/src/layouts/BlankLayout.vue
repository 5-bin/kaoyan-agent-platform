<template>
  <div class="blank">
    <router-view />
  </div>
</template>

<script setup lang="ts"></script>

<style scoped>
.blank {
  min-height: 100vh;
  background:
    radial-gradient(1200px 600px at 10% -10%, rgba(79, 110, 247, 0.18), transparent),
    radial-gradient(900px 500px at 110% 110%, rgba(139, 92, 246, 0.18), transparent),
    #f4f5fb;
}
</style>
