<template>
  <div class="profile-page">
    <el-card class="profile-card" shadow="always">
      <template #header>
        <div class="profile-header">
          <span>个人信息 / 服务配置</span>
          <span class="hint">保存后会写入服务端配置并立即生效，重启后依然保留</span>
        </div>
      </template>

      <el-form :model="form" label-position="top" class="profile-form">
        <el-alert type="info" :closable="false" show-icon class="secret-tip"
          title="出于安全考虑，API Key 已脱敏展示；留空或显示 **** 时表示保留原值，不会覆盖服务器现有配置。" />

        <el-divider content-position="left">大模型服务</el-divider>

        <el-form-item label="大模型 API Key">
          <el-input v-model="form.openai_api_key" type="password" show-password placeholder="如需修改请填入新的 Key" />
        </el-form-item>

        <el-form-item label="大模型 API 地址">
          <el-input v-model="form.openai_base_url" placeholder="例如：https://api.siliconflow.cn/v1" />
        </el-form-item>

        <el-form-item label="大模型模型名">
          <el-input v-model="form.openai_model" placeholder="例如：deepseek-ai/DeepSeek-V3 或 gpt-4o-mini" />
        </el-form-item>

        <el-form-item label="大模型 Temperature">
          <el-input v-model="form.openai_temperature" placeholder="例如：0.2（越低越稳定，越高越创意）" />
        </el-form-item>

        <el-divider content-position="left">高德地图</el-divider>

        <el-form-item label="高德 Web API Key">
          <el-input v-model="form.amap_web_key" type="password" show-password placeholder="如需修改请填入新的 Key" />
        </el-form-item>

        <el-form-item label="高德 JS API Key">
          <el-input v-model="form.amap_js_key" type="password" show-password placeholder="如需修改请填入新的 Key" />
        </el-form-item>

        <el-divider content-position="left">Tavily 网页搜索（景点攻略 / 评价）</el-divider>

        <el-form-item label="Tavily API Key">
          <el-input v-model="form.tavily_api_key" type="password" show-password placeholder="用于联网检索景点评价与攻略" />
        </el-form-item>

        <el-form-item label="Tavily MCP 启动命令">
          <el-input v-model="form.tavily_mcp_command" placeholder="例如：tavily-mcp、npx -y tavily-mcp、uvx tavily-mcp" />
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
  openai_model: '',
  openai_temperature: '',
  amap_web_key: '',
  amap_js_key: '',
  tavily_api_key: '',
  tavily_mcp_command: '',
})

const _fillForm = (config) => {
  form.openai_api_key = config.openai_api_key || ''
  form.openai_base_url = config.openai_base_url || ''
  form.openai_model = config.openai_model || ''
  form.openai_temperature = String(config.openai_temperature ?? '')
  form.amap_web_key = config.amap_web_key || ''
  form.amap_js_key = config.amap_js_key || ''
  form.tavily_api_key = config.tavily_api_key || ''
  form.tavily_mcp_command = config.tavily_mcp_command || 'tavily-mcp'
}

const loadConfig = async () => {
  try {
    const config = await configApi.getRuntimeConfig()
    _fillForm(config)
  } catch (error) {
    ElMessage.error('读取配置失败')
  }
}

const saveConfig = async () => {
  saving.value = true
  try {
    // 脱敏占位符（含 ****）或空值视为"不修改"，提交前清掉，避免覆盖服务器真实 Key
    const payload = {
      openai_api_key: /[*]{2,}/.test(form.openai_api_key) ? '' : form.openai_api_key,
      openai_base_url: form.openai_base_url,
      amap_web_key: /[*]{2,}/.test(form.amap_web_key) ? '' : form.amap_web_key,
      amap_js_key: /[*]{2,}/.test(form.amap_js_key) ? '' : form.amap_js_key,
      tavily_api_key: /[*]{2,}/.test(form.tavily_api_key) ? '' : form.tavily_api_key,
      tavily_mcp_command: form.tavily_mcp_command,
    }
    await configApi.saveRuntimeConfig(payload)
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
.profile-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.hint { color: #64748b; font-size: 12px; }
.profile-form { display: grid; gap: 6px; }
.secret-tip { margin-bottom: 12px; }
.action-row { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 16px; }
</style>
