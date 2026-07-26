<template>
  <div class="auth-page">
    <el-card class="auth-card" shadow="always">
      <template #header>
        <div class="card-header">
          <span>注册账号</span>
          <el-button link type="primary" @click="goLogin">返回登录</el-button>
        </div>
      </template>

      <el-form :model="form" label-position="top" class="auth-form" @submit.prevent>
        <el-form-item label="用户名">
          <el-input v-model="form.username" size="large" placeholder="请输入用户名" />
        </el-form-item>

        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" size="large" show-password placeholder="请输入密码" />
        </el-form-item>

        <el-form-item label="邮箱">
          <el-input v-model="form.email" size="large" placeholder="请输入邮箱" />
        </el-form-item>

        <el-button type="primary" size="large" class="submit-btn" :loading="loading" @click="submit">
          立即注册
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'

const router = useRouter()
const loading = ref(false)
const form = reactive({ username: '', password: '', email: '' })

const goLogin = () => {
  router.push('/login')
}

const submit = async () => {
  loading.value = true
  try {
    await authApi.register(form)
    router.push('/login')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page { min-height: 100vh; display: grid; place-items: center; background: linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%); padding: 24px; }
.auth-card { width: min(480px, 100%); border-radius: 12px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.auth-form { display: grid; gap: 6px; }
.submit-btn { width: 100%; margin-top: 8px; }
</style>
