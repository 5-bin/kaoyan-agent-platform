import { onMounted, ref } from 'vue'
import { getAuthConfig } from '@/api/auth'

/** Registration stays closed until the server positively enables it. */
export function useRegistration() {
  const registrationEnabled = ref(false)
  const registrationMessage = ref('正在获取注册状态…')
  onMounted(async () => {
    try {
      const config = await getAuthConfig()
      registrationEnabled.value = config.registrationEnabled === true
      registrationMessage.value = registrationEnabled.value ? '' : '当前暂不开放注册'
    } catch {
      registrationMessage.value = '暂无法获取注册状态，请稍后重试'
    }
  })
  return { registrationEnabled, registrationMessage }
}
