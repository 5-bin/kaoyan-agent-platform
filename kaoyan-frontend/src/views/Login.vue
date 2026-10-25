<template>
  <div class="wrap">
    <div class="left">
      <div class="brand">
        <span class="mark">考</span>
        <span class="name">考研 Agent 平台</span>
      </div>
      <h1 class="headline">智能刷题，<br/>上岸更近一步</h1>
      <p class="desc">AI 智能组卷 · 错题自动归集 · 择校推荐 · 学习数据看板</p>
      <div class="dots">
        <span>✓ 来源可查的课程习题</span>
        <span>✓ 实时解析</span>
        <span>✓ 个性化推荐</span>
      </div>
    </div>

    <div class="right">
      <div class="panel">
        <h2 class="title">欢迎回来</h2>
        <p class="sub">登录你的账号继续备考</p>

        <el-form :model="form" :rules="rules" ref="formRef" @keyup.enter="onSubmit">
          <el-form-item prop="username">
            <el-input v-model="form.username" size="large" placeholder="用户名" :prefix-icon="User" />
          </el-form-item>
          <el-form-item prop="password">
            <el-input v-model="form.password" type="password" size="large" show-password placeholder="密码" :prefix-icon="Lock" />
          </el-form-item>
          <el-button type="primary" size="large" class="btn" :loading="loading" @click="onSubmit">
            登 录
          </el-button>
        </el-form>

        <div class="foot">
          还没有账号？<router-link to="/register">立即注册</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage, type FormInstance } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const onSubmit = async () => {
  await formRef.value?.validate()
  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push((route.query.redirect as string) || '/')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.wrap {
  min-height: 100vh; display: flex;
  background: var(--c-surface);
}
.left {
  flex: 1; padding: 60px; color: #fff;
  background: linear-gradient(135deg, #3b6cff 0%, #6d5cff 100%);
  display: flex; flex-direction: column; justify-content: center;
}
.brand { display: flex; align-items: center; gap: 10px; margin-bottom: 60px; }
.mark {
  width: 40px; height: 40px; border-radius: 10px;
  background: rgba(255,255,255,.2); display: grid; place-items: center; font-weight: 700;
}
.name { font-weight: 600; }
.headline { font-size: 40px; line-height: 1.3; margin: 0 0 16px; font-weight: 700; }
.desc { opacity: .85; font-size: 15px; margin: 0 0 32px; }
.dots { display: flex; gap: 20px; font-size: 13px; opacity: .9; }

.right {
  width: 480px; flex-shrink: 0;
  display: grid; place-items: center; padding: 40px;
}
.panel { width: 100%; max-width: 360px; }
.title { font-size: 26px; margin: 0 0 6px; }
.sub { color: var(--c-ink-2); margin: 0 0 28px; }
.btn { width: 100%; }
.foot { text-align: center; margin-top: 18px; color: var(--c-ink-2); font-size: 13px; }
</style>
