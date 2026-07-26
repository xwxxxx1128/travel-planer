<template>
  <div class="auth-page">
    <div class="auth-shell">
      <div class="auth-hero">
        <div class="brand">Trip plan AI</div>
        <h1>地图选点，路线一键规划</h1>
        <p>支持搜索景区、直接在地图上点选目的地，并把多个地点串成更顺路的行程。</p>
      </div>

      <el-card class="auth-card" shadow="always">
        <template #header>
          <div class="card-header">
            <span>登录</span>
            <el-button link type="primary" @click="goRegister">没有账号？去注册</el-button>
          </div>
        </template>

        <el-form :model="form" label-position="top" class="auth-form" @submit.prevent>
          <el-form-item label="用户名">
            <el-input v-model="form.username" size="large" placeholder="请输入用户名" />
          </el-form-item>

          <el-form-item label="密码">
            <el-input v-model="form.password" type="password" size="large" show-password placeholder="请输入密码" />
          </el-form-item>

          <el-button type="primary" size="large" class="submit-btn" :loading="loading" @click="submit">
            进入地图选点
          </el-button>

          <div class="auth-footer">
            <span>还没有账号？</span>
            <el-button link type="primary" @click="goRegister">立即注册</el-button>
          </div>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const store = useUserStore()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

const goRegister = () => {
  router.push('/register')
}

const submit = async () => {
  loading.value = true
  try {
    const res = await authApi.login(form)
    store.login(res.access_token, res.user)
    router.push('/route-planner')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page { min-height: 100vh; display: grid; place-items: center; background: radial-gradient(circle at top, rgba(64, 158, 255, 0.16), transparent 35%), linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%); padding: 24px; }
.auth-shell { width: min(960px, 100%); display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 24px; align-items: center; }
.auth-hero { color: #1f2937; padding: 16px 8px; }
.brand { display: inline-flex; align-items: center; padding: 6px 12px; border-radius: 999px; background: rgba(64, 158, 255, 0.1); color: #409eff; font-weight: 700; margin-bottom: 16px; }
.auth-hero h1 { margin: 0 0 12px; font-size: 40px; line-height: 1.15; }
.auth-hero p { margin: 0; max-width: 420px; color: #64748b; font-size: 16px; line-height: 1.8; }
.auth-card { width: 100%; border-radius: 12px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.auth-form { display: grid; gap: 6px; }
.submit-btn { width: 100%; margin-top: 8px; }
.auth-footer { display: flex; justify-content: center; align-items: center; gap: 4px; margin-top: 6px; color: #64748b; font-size: 14px; }
@media (max-width: 900px) { .auth-shell { grid-template-columns: 1fr; } .auth-hero { text-align: center; } .auth-hero p { margin: 0 auto; } }
</style>
