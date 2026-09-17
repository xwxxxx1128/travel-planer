<template>
  <div class="flights-page">
    <div class="page-header">
      <div class="header-left">
        <el-button text class="back-btn" @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回地图
        </el-button>
        <h2>我的航班</h2>
        <p>这里只显示你自己账号下的航班订单（由 AI 助手在对话中为你预订，各账号互不影响）</p>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="goChat">
          <el-icon><Promotion /></el-icon>
          去对话里订机票
        </el-button>
      </div>
    </div>

    <div class="page-body">
      <div v-loading="loading" class="list-wrap">
        <el-empty
          v-if="!loading && !items.length"
          description="还没有航班订单，去对话里说「帮我订一张北京到上海的机票」试试"
        />
        <div v-else class="flight-list">
          <div v-for="item in items" :key="item.id" class="flight-card">
            <div class="flight-main">
              <div class="flight-title">
                <span class="flight-no">{{ item.flight_no }}</span>
                <el-tag size="small" type="success" effect="light">
                  {{ item.departure_city }} → {{ item.arrival_city }}
                </el-tag>
                <el-tag v-if="item.booking_no" size="small" type="info" effect="plain">
                  订单号 {{ item.booking_no }}
                </el-tag>
              </div>
              <div class="flight-time">
                <span>起飞 {{ item.depart_time }}</span>
                <span>到达 {{ item.arrive_time }}</span>
              </div>
              <div v-if="item.price !== null && item.price !== undefined" class="flight-price">
                价格 ¥{{ item.price }}
              </div>
            </div>
            <el-button text type="danger" class="cancel-btn" @click="onCancel(item)">
              <el-icon><Delete /></el-icon>
              取消
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Delete, Promotion } from '@element-plus/icons-vue'
import { travelApi } from '@/api/travel'

const router = useRouter()
const loading = ref(false)
const items = ref([])

const load = async () => {
  loading.value = true
  try {
    const res = await travelApi.flightList()
    const list = Array.isArray(res) ? res : (res && res.data) || []
    items.value = list
  } catch (e) {
    // 拦截器已统一提示
  } finally {
    loading.value = false
  }
}

const onCancel = async (item) => {
  try {
    await ElMessageBox.confirm(`确定要取消「${item.flight_no}」这笔订单吗？`, '取消确认', {
      confirmButtonText: '取消订单',
      cancelButtonText: '再想想',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await travelApi.flightCancel(item.id)
    ElMessage.success('已取消该航班订单')
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
.flights-page {
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
}
.list-wrap {
  min-height: 200px;
}
.flight-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.flight-card {
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
.flight-main {
  flex: 1;
  min-width: 0;
}
.flight-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.flight-no {
  font-size: 15px;
  font-weight: 600;
  color: #409eff;
}
.flight-time {
  margin-top: 6px;
  font-size: 13px;
  color: #475569;
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}
.flight-price {
  margin-top: 4px;
  font-size: 12px;
  color: #94a3b8;
}
.cancel-btn {
  flex-shrink: 0;
}
</style>
