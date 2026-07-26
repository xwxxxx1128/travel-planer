<template>
  <div class="profile-page">
    <el-card class="profile-card" shadow="always">
      <template #header>
        <div class="profile-header">
          <span>个人信息 / 服务配置</span>
          <span class="hint">保存后会写入 `.env` 并立即生效</span>
        </div>
      </template>

      <el-form :model="form" label-position="top" class="profile-form">
        <el-form-item label="大模型 API Key">
          <el-input v-model="form.openai_api_key" type="password" show-password placeholder="请输入大模型 API Key" />
        </el-form-item>

        <el-form-item label="大模型 API 地址">
          <el-input v-model="form.openai_base_url" placeholder="例如：https://api.openai.com/v1" />
        </el-form-item>

        <el-form-item label="高德 Web API Key">
          <el-input v-model="form.amap_web_key" type="password" show-password placeholder="请输入高德 Web API Key" />
        </el-form-item>

        <el-form-item label="高德 JS API Key">
          <el-input v-model="form.amap_js_key" type="password" show-password placeholder="请输入高德 JS API Key" />
        </el-form-item>

        <div class="action-row">
          <el-button type="primary" :loading="saving" @click="saveConfig">保存配置</el-button>
          <el-button @click="loadConfig">重新读取</el-button>
          <el-button text @click="goToRoutePlanner">返回地图页</el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { configApi } from '@/api/config'

const router = useRouter()
const saving = ref(false)
const form = reactive({
  openai_api_key: '',
  openai_base_url: '',
  amap_web_key: '',
  amap_js_key: '',
})

const loadConfig = async () => {
  try {
    const config = await configApi.getRuntimeConfig()
    form.openai_api_key = config.openai_api_key || ''
    form.openai_base_url = config.openai_base_url || ''
    form.amap_web_key = config.amap_web_key || ''
    form.amap_js_key = config.amap_js_key || ''
  } catch (error) {
    ElMessage.error('读取配置失败')
  }
}

const saveConfig = async () => {
  saving.value = true
  try {
    await configApi.saveRuntimeConfig(form)
    ElMessage.success('配置已保存')
    await loadConfig()
  } catch (error) {
    ElMessage.error('保存配置失败')
  } finally {
    saving.value = false
  }
}

const goToRoutePlanner = () => {
  router.push('/route-planner')
}

onMounted(loadConfig)
</script>

<style scoped>
.profile-page { min-height: 100vh; padding: 24px; background: linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%); }
.profile-card { max-width: 760px; margin: 0 auto; border-radius: 12px; }
.profile-header { display: flex; align-items: center; justify-content: space-between; }
.hint { color: #64748b; font-size: 12px; }
.profile-form { display: grid; gap: 6px; }
.action-row { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; }
</style>
