<template>
  <div class="wrap">
    <div class="left">
      <div class="brand">
        <span class="mark">考</span>
        <span class="name">考研 Agent 平台</span>
      </div>
      <h1 class="headline">开启你的<br/>智能备考之旅</h1>
      <p class="desc">注册即可使用智能刷题、错题归集、择校推荐等全部功能</p>
    </div>
    <div class="right">
      <div class="panel">
        <h2 class="title">创建账号</h2>
        <p class="sub">注册后自动登录</p>
        <el-form :model="form" :rules="rules" ref="formRef">
          <el-form-item prop="username">
            <el-input v-model="form.username" size="large" placeholder="用户名（3-64 位）" :prefix-icon="User" />
          </el-form-item>
          <el-form-item prop="password">
            <el-input v-model="form.password" type="password" size="large" show-password placeholder="密码（6-32 位）" :prefix-icon="Lock" />
          </el-form-item>
          <el-form-item prop="confirm">
            <el-input v-model="form.confirm" type="password" size="large" show-password placeholder="确认密码" :prefix-icon="Lock" />
          </el-form-item>
          <el-button type="primary" size="large" class="btn" :loading="loading" @click="onSubmit">注 册</el-button>
        </el-form>
        <div class="foot">已有账号？<router-link to="/login">直接登录</router-link></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage, type FormInstance } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({ username: '', password: '', confirm: '' })
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 64, message: '用户名 3-64 位', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 32, message: '密码 6-32 位', trigger: 'blur' }
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: (_r: any, v: string, cb: any) => (v === form.password ? cb() : cb(new Error('两次密码不一致'))), trigger: 'blur' }
  ]
}
const onSubmit = async () => {
  await formRef.value?.validate()
  loading.value = true
  try {
    await userStore.register(form.username, form.password)
    ElMessage.success('注册成功')
    router.push('/')
  } finally { loading.value = false }
}
</script>

<style scoped lang="scss">
.wrap { min-height: 100vh; display: flex; background: var(--c-surface); }
.left {
  flex: 1; padding: 60px; color: #fff;
  background: linear-gradient(135deg, #3b6cff 0%, #6d5cff 100%);
  display: flex; flex-direction: column; justify-content: center;
}
.brand { display: flex; align-items: center; gap: 10px; margin-bottom: 60px; }
.mark { width: 40px; height: 40px; border-radius: 10px; background: rgba(255,255,255,.2); display: grid; place-items: center; font-weight: 700; }
.name { font-weight: 600; }
.headline { font-size: 40px; line-height: 1.3; margin: 0 0 16px; font-weight: 700; }
.desc { opacity: .85; font-size: 15px; margin: 0; }
.right { width: 480px; flex-shrink: 0; display: grid; place-items: center; padding: 40px; }
.panel { width: 100%; max-width: 360px; }
.title { font-size: 26px; margin: 0 0 6px; }
.sub { color: var(--c-ink-2); margin: 0 0 28px; }
.btn { width: 100%; }
.foot { text-align: center; margin-top: 18px; color: var(--c-ink-2); font-size: 13px; }
</style>
