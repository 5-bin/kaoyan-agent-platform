<template>
  <AuthLayout slogan="开启你的智能备考之旅" desc="来源可查的课程习题与学习数据看板">
    <h2 class="title">{{ registrationEnabled ? '创建账号' : '注册状态' }}</h2>
    <p class="sub">{{ registrationEnabled ? '注册后自动登录' : registrationMessage }}</p>
    <el-form v-if="registrationEnabled" :model="form" :rules="rules" ref="formRef">
      <el-form-item prop="username">
        <el-input v-model="form.username" size="large" placeholder="用户名（3-64 位）" :prefix-icon="User" />
      </el-form-item>
      <el-form-item prop="password">
        <el-input v-model="form.password" type="password" size="large" show-password placeholder="密码（6-32 位）" :prefix-icon="Lock" />
      </el-form-item>
      <el-form-item prop="confirm">
        <el-input v-model="form.confirm" type="password" size="large" show-password placeholder="确认密码" :prefix-icon="Lock" />
      </el-form-item>
      <el-button type="primary" size="large" round class="btn" :loading="loading" @click="onSubmit">注 册</el-button>
    </el-form>
    <div class="foot">已有账号？<router-link to="/login">直接登录</router-link></div>
  </AuthLayout>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import AuthLayout from '@/components/AuthLayout.vue'
import { useRegistration } from '@/composables/useRegistration'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage, type FormInstance } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

const { registrationEnabled, registrationMessage } = useRegistration()
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
  if (!registrationEnabled.value) return
  await formRef.value?.validate()
  loading.value = true
  try {
    await userStore.register(form.username, form.password)
    ElMessage.success('注册成功')
    router.push('/tasks')
  } finally { loading.value = false }
}
</script>
