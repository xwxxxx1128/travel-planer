<template>
  <div class="travel-list-page">
    <div class="page-header">
      <div class="header-left">
        <el-button text class="back-btn" @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回地图
        </el-button>
        <h2>我的旅行清单</h2>
        <p>把想去的地方收进来，随时查看与管理</p>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="goChat">
          <el-icon><Promotion /></el-icon>
          让 AI 推荐景点
        </el-button>
      </div>
    </div>

    <div class="page-body">
      <el-card class="add-card" shadow="never">
        <div class="add-row">
          <el-input
            v-model="form.name"
            placeholder="想去的地点，例如：宽窄巷子"
            class="add-name"
            @keyup.enter="onAdd"
          />
          <el-input v-model="form.city" placeholder="城市（可选）" class="add-city" @keyup.enter="onAdd" />
          <el-input v-model="form.note" placeholder="备注（可选）" class="add-note" @keyup.enter="onAdd" />
          <el-button type="primary" :loading="adding" @click="onAdd">
            <el-icon><Plus /></el-icon>
            添加
          </el-button>
        </div>
      </el-card>

      <div v-loading="loading" class="list-wrap">
        <el-empty v-if="!loading && !items.length" description="清单还是空的，先添加一个想去的地方吧" />
        <div v-else class="wish-list">
          <div v-for="item in items" :key="item.id" class="wish-card">
            <div class="wish-main">
              <div class="wish-title">
                <span class="wish-name">{{ item.name }}</span>
                <el-tag v-if="item.city" size="small" type="success" effect="light">{{ item.city }}</el-tag>
                <el-tag size="small" :type="sourceType(item.source)" effect="plain">
                  {{ sourceText(item.source) }}
                </el-tag>
              </div>
              <div v-if="item.address" class="wish-addr">
                <el-icon><Location /></el-icon>
                {{ item.address }}
              </div>
              <div v-if="item.note" class="wish-note">备注：{{ item.note }}</div>
            </div>
            <el-button text type="danger" class="remove-btn" @click="onRemove(item)">
              <el-icon><Delete /></el-icon>
              移出
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Plus, Delete, Location, Promotion } from '@element-plus/icons-vue'
import { travelApi } from '@/api/travel'

const router = useRouter()
const loading = ref(false)
const adding = ref(false)
const items = ref([])
const form = reactive({ name: '', city: '', note: '' })

const SOURCE_TEXT = { assistant: '对话加入', recommend: '推荐加入', manual: '手动添加' }
const sourceText = (s) => SOURCE_TEXT[s] || '手动添加'
const sourceType = (s) => (s === 'manual' ? 'info' : 'warning')

const load = async () => {
  loading.value = true
  try {
    const res = await travelApi.wishlistList()
    const list = Array.isArray(res) ? res : (res && res.data) || []
    items.value = list
  } catch (e) {
    // 拦截器已统一提示
  } finally {
    loading.value = false
  }
}

const onAdd = async () => {
  const name = form.name.trim()
  if (!name) {
    ElMessage.warning('请输入地点名称')
    return
  }
  adding.value = true
  try {
    await travelApi.wishlistAdd({
      name,
      city: form.city.trim() || null,
      note: form.note.trim() || null,
      source: 'manual',
    })
    ElMessage.success('已加入旅行清单')
    form.name = ''
    form.city = ''
    form.note = ''
    await load()
  } catch (e) {
    // 拦截器已统一提示
  } finally {
    adding.value = false
  }
}

const onRemove = async (item) => {
  try {
    await ElMessageBox.confirm(`确定要把「${item.name}」移出旅行清单吗？`, '移出确认', {
      confirmButtonText: '移出',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await travelApi.wishlistRemove(item.id)
    ElMessage.success('已移出')
    await load()
  } catch (e) {
    // 拦截器已统一提示
  }
}

const goBack = () => router.push('/route-planner')
const goChat = () => router.push('/chat')

onMounted(load)
</script>

<style scoped>
.travel-list-page {
  min-height: 100vh;
  padding: 24px;
  background: linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
}
.page-header {
  max-width: 960px;
  margin: 0 auto 16px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.header-left h2 {
  margin: 8px 0 2px;
  font-size: 22px;
  color: #1f2d3d;
}
.header-left p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}
.back-btn {
  padding-left: 0;
  color: #64748b;
}
.page-body {
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.add-card {
  border-radius: 12px;
}
.add-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.add-name { flex: 2; min-width: 220px; }
.add-city { flex: 1; min-width: 140px; }
.add-note { flex: 2; min-width: 180px; }
.list-wrap {
  min-height: 200px;
}
.wish-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.wish-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 18px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}
.wish-main {
  flex: 1;
  min-width: 0;
}
.wish-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.wish-name {
  font-size: 15px;
  font-weight: 600;
  color: #1f2d3d;
}
.wish-addr {
  margin-top: 6px;
  font-size: 13px;
  color: #475569;
  display: flex;
  align-items: center;
  gap: 4px;
}
.wish-note {
  margin-top: 4px;
  font-size: 12px;
  color: #94a3b8;
}
.remove-btn {
  flex-shrink: 0;
}
</style>
