<template>
  <AuthLayout slogan="智能刷题，上岸更近一步" desc="AI 智能组卷 · 错题自动归集 · 择校推荐 · 学习数据看板" :features="features">
    <h2 class="title">欢迎回来</h2>
    <p class="sub">登录你的账号继续备考</p>

    <el-form :model="form" :rules="rules" ref="formRef" @keyup.enter="onSubmit">
      <el-form-item prop="username">
        <el-input v-model="form.username" size="large" placeholder="用户名" :prefix-icon="User" />
      </el-form-item>
      <el-form-item prop="password">
        <el-input v-model="form.password" type="password" size="large" show-password placeholder="密码" :prefix-icon="Lock" />
      </el-form-item>
      <el-button type="primary" size="large" round class="btn" :loading="loading" @click="onSubmit">
        登 录
      </el-button>
    </el-form>

    <div v-if="registrationEnabled" class="foot">
      还没有账号？<router-link to="/register">立即注册</router-link>
    </div>
    <div v-else class="foot">{{ registrationMessage }}，已有账号可正常登录。</div>
  </AuthLayout>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import AuthLayout from '@/components/AuthLayout.vue'
import { useRegistration } from '@/composables/useRegistration'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage, type FormInstance } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

const { registrationEnabled, registrationMessage } = useRegistration()
const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const features = ['来源可查的课程习题', '实时解析', '个性化推荐']

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
    const destination = route.query.redirect as string | undefined
    router.push(destination && destination !== '/' ? destination : '/tasks')
  } finally {
    loading.value = false
  }
}
</script>
