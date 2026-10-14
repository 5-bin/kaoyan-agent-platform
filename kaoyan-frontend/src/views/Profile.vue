<template>
  <div class="page">
    <div class="page-head">
      <h2 class="page-title">个人中心</h2>
      <p class="page-sub">管理账号信息与备考档案</p>
    </div>

    <div class="card head">
      <el-avatar :size="64" :src="userStore.userInfo?.avatarUrl" class="big">
        {{ userStore.userInfo?.username?.[0]?.toUpperCase() }}
      </el-avatar>
      <div class="head-info">
        <div class="uname">{{ userStore.userInfo?.username }}</div>
        <el-tag size="small" style="margin-top:6px">{{ userStore.userInfo?.role }}</el-tag>
      </div>
      <el-upload :show-file-list="false" :http-request="upload">
        <el-button>更换头像</el-button>
      </el-upload>
    </div>

    <div class="card" style="margin-top:16px">
      <h3 class="sec-title">备考档案</h3>
      <el-form :model="profile" label-width="100px" style="max-width:560px">
        <el-form-item label="目标院校">
          <el-input v-model="profile.targetSchool" />
        </el-form-item>
        <el-form-item label="目标专业">
          <el-input v-model="profile.targetMajor" />
        </el-form-item>
        <el-form-item label="考试年份">
          <el-input v-model.number="profile.examYear" type="number" />
        </el-form-item>
        <el-form-item label="背景说明">
          <el-input v-model="profile.background" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label=" ">
          <el-button type="primary" size="large" :loading="saving" @click="save">保存档案</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { updateProfile, updateAvatar } from '@/api/user'
import { uploadFile } from '@/api/file'
import { ElMessage } from 'element-plus'

const userStore = useUserStore()
const saving = ref(false)
const profile = reactive({
  targetSchool: userStore.userInfo?.targetSchool || '',
  targetMajor: userStore.userInfo?.targetMajor || '',
  examYear: userStore.userInfo?.examYear as any,
  background: userStore.userInfo?.background || ''
})

const save = async () => {
  saving.value = true
  try {
    await updateProfile({ ...profile })
    await userStore.refreshUserInfo()
    ElMessage.success('已保存')
  } finally { saving.value = false }
}
const upload = async (opt: any) => {
  const r = await uploadFile(opt.file, 'avatar')
  await updateAvatar({ avatarUrl: r.url })
  await userStore.refreshUserInfo()
  ElMessage.success('头像已更新')
}
</script>

<style scoped>
.head { display: flex; align-items: center; padding: 24px; }
.big { background: var(--c-primary); color: #fff; }
.head-info { margin-left: 16px; flex: 1; }
.uname { font-size: 18px; font-weight: 700; }
.sec-title { font-size: 15px; font-weight: 600; margin: 0 0 16px; }
</style>
