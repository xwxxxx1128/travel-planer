<template>
  <div class="chat-container">
    <!-- 顶部导航栏 -->
    <div class="chat-header">
      <div class="header-left">
        <h2>AI智能助手</h2>
        <p>智能问答 · 航班查询 · 酒店搜索(高德) · 景点推荐</p>
      </div>
      <div class="header-right">
        <el-button @click="goToRoutePlanner" type="default" class="map-btn">
          <el-icon><Location /></el-icon>
          地图规划
        </el-button>
        <el-dropdown @command="handleCommand">
          <span class="el-dropdown-link">
            <el-icon><User /></el-icon>
            {{ userStore.userInfo?.username || '用户' }}
            <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 主内容区域 -->
    <div class="chat-content">
      <!-- 左侧功能菜单 -->
      <div class="chat-sidebar">
        <div class="sidebar-header">
          <h3>可用功能</h3>
        </div>
        <el-menu :default-active="activeMenu" class="sidebar-menu">
          <el-menu-item index="1" @click="quickAction('帮我查询从北京到上海的航班')">
            <el-icon><Location /></el-icon>
            <span>航班服务</span>
          </el-menu-item>
          <el-menu-item index="2" @click="askHotel">
            <el-icon><House /></el-icon>
            <span>酒店服务</span>
          </el-menu-item>
          <el-menu-item index="3" @click="askAttraction">
            <el-icon><Sunny /></el-icon>
            <span>旅游景点</span>
          </el-menu-item>
          <el-menu-item index="4" @click="askReview">
            <el-icon><Star /></el-icon>
            <span>景点评价</span>
          </el-menu-item>
        </el-menu>
      </div>

      <!-- 右侧聊天区域 -->
      <div class="chat-main">
        <div class="chat-messages" ref="messagesContainer">
          <div
            v-for="(message, index) in messages"
            :key="index"
            :class="['message', message.role]"
          >
            <div class="message-content">
              <div class="message-avatar">
                <el-icon v-if="message.role === 'user'"><User /></el-icon>
                <span v-else>AI</span>
              </div>
              <div class="message-text">
                <div v-if="message.loading" class="loading-dots">
                  <span></span><span></span><span></span>
                </div>
                <template v-else>
                  <p class="message-paragraph">{{ message.text }}</p>
                  <div v-if="message.reviews && message.reviews.length" class="review-list">
                    <div v-for="(rv, i) in message.reviews" :key="i" class="review-card">
                      <div class="review-head">
                        <span v-if="rv.rating" class="review-rating">★ {{ rv.rating }}</span>
                        <el-tag v-if="rv.label" size="small" type="warning" effect="light">{{ rv.label }}</el-tag>
                        <span class="review-source">{{ rv.source === 'sample' ? '离线样例' : '实时爬取' }}</span>
                      </div>
                      <div class="review-content">{{ rv.content }}</div>
                    </div>
                  </div>
                  <div v-if="message.flights && message.flights.length" class="flight-list">
                    <div v-for="(ft, i) in message.flights" :key="i" class="flight-card">
                      <div class="flight-head">
                        <span class="flight-no">{{ ft.flight_no }}</span>
                        <el-tag size="small" type="success" effect="light">{{ ft.status }}</el-tag>
                      </div>
                      <div class="flight-route">
                        <span class="flight-airport">{{ ft.departure }}</span>
                        <span class="flight-arrow">✈</span>
                        <span class="flight-airport">{{ ft.arrival }}</span>
                      </div>
                      <div class="flight-time">
                        <span>起飞 {{ ft.dep_time }}</span>
                        <span>到达 {{ ft.arr_time }}</span>
                      </div>
                    </div>
                  </div>
                  <div v-if="message.hotels && message.hotels.length" class="hotel-list">
                    <div v-for="(ht, i) in message.hotels" :key="i" class="hotel-card">
                      <div class="hotel-head">
                        <span class="hotel-name">{{ ht.name }}</span>
                        <el-tag v-if="ht.rating" size="small" type="warning" effect="light">★ {{ ht.rating }}</el-tag>
                      </div>
                      <div class="hotel-meta">
                        <span v-if="ht.type" class="hotel-type">{{ ht.type }}</span>
                        <span v-if="ht.cost" class="hotel-cost">人均 {{ ht.cost }}</span>
                      </div>
                      <div class="hotel-address">📍 {{ ht.address || '地址未知' }}</div>
                      <div v-if="ht.tel" class="hotel-tel">☎ {{ ht.tel }}</div>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>

        <div class="chat-input">
          <el-input
            v-model="input"
            placeholder="请输入您的问题，例如：帮我查询从北京到上海的航班"
            @keyup.enter="ask"
            size="large"
          >
            <template #append>
              <el-button @click="ask" type="primary" :disabled="loading">
                <el-icon><Promotion /></el-icon>
                发送
              </el-button>
            </template>
          </el-input>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, ArrowDown, House, Location, Promotion, Star, Sunny } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { travelApi } from '@/api/travel'

const router = useRouter()
const userStore = useUserStore()

const input = ref('')
const loading = ref(false)
const messages = ref([{ role: 'assistant', text: '您好！我是AI智能助手。您可以：\n• 查询航班（如：从北京到上海的航班）\n• 搜索酒店（数据来自高德地图实时POI）\n• 让我推荐景点（如：我想到成都去玩，推荐一下景点）\n• 查询景点评价（如：故宫的评价）\n请问有什么可以帮您的？' }])
const activeMenu = ref('1')
const messagesContainer = ref(null)

// 页面加载即恢复持久化对话（刷新不丢），并恢复刷新前未完成的“待确认”弹窗
onMounted(async () => {
  // 优先用 localStorage 中记录的会话 id：与聊天时写入的完全一致，
  // 避免 store 水合时机差异导致“保存/读取”用了不同 session_id 而读不到历史
  const sessionId =
    localStorage.getItem('chat_session_id') ||
    userStore.userInfo?.username ||
    'demo'
  try {
    const res = await travelApi.getHistory(sessionId)
    // 兼容拦截器返回结构：{messages:[...]} 或直接 axios 响应 {data:{messages}}
    const hist = (res && res.messages) || (res && res.data && res.data.messages) || []
    if (Array.isArray(hist) && hist.length) {
      messages.value = hist.map((m) => ({
        role: m.role,
        text: m.text,
        reviews: m.reviews || [],
        flights: m.flights || [],
        hotels: m.hotels || [],
      }))
      await nextTick()
      scrollToBottom()
    }
  } catch (e) {
    // 无历史则保留欢迎语
  }

  try {
    const pend = await travelApi.pendingChat(sessionId)
    const pendData = pend && (pend.data || pend)
    if (pendData && pendData.interrupted && pendData.payload) {
      messages.value.push({ role: 'assistant', text: pendData.resume_reply || '请确认操作' })
      const idx = messages.value.length
      messages.value.push({ role: 'assistant', text: '', loading: true })
      scrollToBottom()
      await handleSensitiveConfirm(pendData.payload, idx)
    }
  } catch (e) {
    // 忽略
  }
})

const ask = async () => {
  const text = input.value.trim()
  if (!text) {
    ElMessage.warning('请输入消息内容')
    return
  }
  messages.value.push({ role: 'user', text })
  input.value = ''
  scrollToBottom()
  await sendToAssistant(text)
}

const askReview = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入要查询评价的景点名称', '景点评价', {
      confirmButtonText: '查询',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '景点名称不能为空',
    })
    const place = value.trim()
    messages.value.push({ role: 'user', text: `帮我找${place}的评价` })
    scrollToBottom()
    await sendToAssistant(`帮我找${place}的评价`, place)
  } catch {
    // 用户取消
  }
}

const askHotel = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入要搜索酒店的城市，例如：北京', '酒店搜索（高德地图实时POI）', {
      confirmButtonText: '搜索',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '城市名称不能为空',
    })
    const city = value.trim()
    messages.value.push({ role: 'user', text: `在${city}搜索酒店` })
    scrollToBottom()
    await sendToAssistant(`在${city}搜索酒店`)
  } catch {
    // 用户取消
  }
}

const askAttraction = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入您想去游玩的城市或目的地', 'AI 景点推荐', {
      confirmButtonText: '推荐',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '目的地不能为空',
    })
    const dest = value.trim()
    messages.value.push({ role: 'user', text: `我想到${dest}去玩，给我推荐一下景点` })
    scrollToBottom()
    await sendToAssistant(`我想到${dest}去玩，给我推荐一下景点`)
  } catch {
    // 用户取消
  }
}

const sendToAssistant = async (text, place = null) => {
  loading.value = true
  const idx = messages.value.length
  messages.value.push({ role: 'assistant', text: '', loading: true })
  scrollToBottom()
  try {
    const passenger = userStore.userInfo?.username || 'demo'
    // 固化会话 id：刷新后用同一个 id 去读历史，保证“保存/读取”成对
    localStorage.setItem('chat_session_id', passenger)
    // 把当前轮之前的完整对话历史传给后端（对话记忆 / Checkpointer 的 history 维度）
    const history = messages.value
      .slice(0, idx)
      .map((m) => ({ role: m.role, text: m.text }))
    const msg = messages.value[idx]
    let escalated = false
    let confirmPayload = null
    let hasText = false // 是否已收到首个真实文本块（用于覆盖初始进度占位）
    // 节点级 SSE：逐块推送，连接持续有字节流动，基本杜绝前台硬超时
    await travelApi.sendChatStream(
      {
        message: text,
        history,
        place,
        passenger,
        session_id: passenger, // 用用户名作为会话 id，驱动域状态栈与中断点恢复
      },
      (ev) => {
        if (!ev || ev.type === undefined) return
        if (ev.type === 'status') {
          // 进度提示：仅在尚无正文时作为占位展示，避免污染最终回复
          if (!hasText) msg.text = ev.text || '思考中…'
        } else if (ev.type === 'delta') {
          // token 级流式增量：逐字追加（不带换行），让首字在秒级出现，消除“一直思考”感
          msg.text = (hasText ? msg.text : '') + (ev.text || '')
          hasText = true
        } else if (ev.type === 'message') {
          // 节点产出的 AI 文本块：首个直接覆盖占位，后续累积拼接
          if (hasText) msg.text = msg.text + '\n' + (ev.text || '')
          else { msg.text = ev.text || ''; hasText = true }
        } else if (ev.type === 'error') {
          msg.text = ev.text || '请求失败，请稍后重试。'
        } else if (ev.type === 'final') {
          // 最终聚合结果：作为权威正文覆盖，并携带结构化字段
          if (ev.reply) { msg.text = ev.reply; hasText = true }
          msg.reviews = ev.reviews || []
          msg.flights = ev.flights || []
          msg.hotels = ev.hotels || []
          escalated = !!ev.escalated
          confirmPayload = ev.confirm || null
        }
        scrollToBottom()
      }
    )

    // 敏感操作（预订 / 取消机票）需要用户二次确认
    if (confirmPayload) {
      await handleSensitiveConfirm(confirmPayload, idx)
    } else if (escalated) {
      // CompleteOrEscalate：子流程结构化交还（转接人工/政策）
      const from = '主助手'
      msg.text = `${msg.text || ''}\n\n（已结构化转接：${from}）`
    }
  } catch (e) {
    const timedOut =
      e?.code === 'ECONNABORTED' ||
      /timeout/i.test(e?.message || '') ||
      e?.response === undefined
    const msg = messages.value[idx]
    if (!msg.text) {
      // 流式连接中断（多为代理/网络超时），但后端很可能已把答案算完并写入历史。
      // 主动拉一次历史：若最后一条正是本次提问对应的助手回复，则直接恢复，
      // 避免“一直思考到超时、刷新后才看到答案”的体验问题。
      try {
        const hist = await travelApi.getHistory(passenger)
        if (Array.isArray(hist) && hist.length) {
          const last = hist[hist.length - 1]
          const lastUserText = hist
            .filter((m) => m.role === 'user')
            .slice(-1)[0]?.text
          if (
            last &&
            last.role === 'assistant' &&
            last.text &&
            lastUserText === text
          ) {
            msg.text = last.text
            msg.reviews = last.reviews || []
            msg.flights = last.flights || []
            msg.hotels = last.hotels || []
            msg.loading = false
            loading.value = false
            scrollToBottom()
            return
          }
        }
      } catch {
        // 恢复失败则走下方兜底提示
      }
      msg.text = timedOut
        ? '请求超时（模型响应较慢或网络不通）。请检查「设置」中的模型配置，或稍后重试。'
        : '请求失败，请确认后端服务已启动（运行 python main.py）。'
    }
  } finally {
    const msg = messages.value[idx]
    if (msg) msg.loading = false
    loading.value = false
    scrollToBottom()
  }
}

// 预订 / 取消机票等敏感操作：先弹确认框，确认后才真正执行写库操作
const handleSensitiveConfirm = async (confirm, idx) => {
  const msg = messages.value[idx]
  let userCancelled = false
  try {
    await ElMessageBox.confirm(
      `请确认${confirm.action === 'book' ? '预订' : '取消'}操作：\n${confirm.summary}`,
      confirm.action === 'book' ? '确认预订机票' : '确认取消机票',
      { confirmButtonText: '确认', cancelButtonText: '再想想', type: 'warning' }
    )
  } catch {
    userCancelled = true
  }
  if (userCancelled) {
    const sessionId = userStore.userInfo?.username || 'demo'
    try {
      await travelApi.resumeChat({ session_id: sessionId, approved: false })
    } catch {
      // 即便恢复接口失败，也只提示已取消
    }
    if (msg) msg.text = `${msg.text || ''}\n\n已取消该操作，未做任何改动。`
    return
  }
  try {
    // 通过 Checkpointer 的 resume 端点恢复被中断的敏感操作（human-in-the-loop）
    const sessionId = userStore.userInfo?.username || 'demo'
    const act = await travelApi.resumeChat({ session_id: sessionId, approved: true })
    if (msg) msg.text = `${msg.text || ''}\n\n${act.reply}`
  } catch {
    if (msg) msg.text = `${msg.text || ''}\n\n操作执行失败，请稍后重试。`
  }
}

const quickAction = (text) => {
  input.value = text
  ask()
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

const handleCommand = async (command) => {
  if (command === 'logout') {
    try {
      await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      })
      userStore.logout()
      ElMessage.success('已退出登录')
      router.push('/login')
    } catch {
    }
  }
}

const goToRoutePlanner = () => {
  router.push('/route-planner')
}
</script>

<style scoped>
.chat-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f5f7fa;
}

.chat-header {
  background-color: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.header-left h2 {
  margin: 0;
  color: #333;
  font-size: 18px;
}

.header-left p {
  margin: 3px 0 0 0;
  color: #666;
  font-size: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 15px;
}

.el-dropdown-link {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 5px;
  color: #333;
}

.chat-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.chat-sidebar {
  width: 200px;
  background-color: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.sidebar-header h3 {
  margin: 0;
  color: #333;
  font-size: 14px;
}

.sidebar-menu {
  border: none;
  flex: 1;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px;
  background-color: #f5f7fa;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 20px;
  padding: 10px;
}

.message {
  margin-bottom: 20px;
}

.message-content {
  display: flex;
  gap: 12px;
  max-width: 70%;
}

.message.user {
  margin-left: auto;
}

.message.user .message-content {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: #409eff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.assistant .message-avatar {
  background-color: #67c23a;
}

.message-text {
  padding: 12px 16px;
  border-radius: 12px;
  background-color: #fff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  word-wrap: break-word;
  line-height: 1.6;
}

.message.user .message-text {
  background-color: #409eff;
  color: #fff;
}

.chat-input {
  background-color: #fff;
  padding: 16px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.message-paragraph {
  margin: 0 0 8px 0;
  white-space: pre-wrap;
}

/* 加载动画 */
.loading-dots {
  display: inline-flex;
  gap: 4px;
  padding: 4px 0;
}
.loading-dots span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background-color: #c0c4cc;
  animation: blink 1.2s infinite ease-in-out both;
}
.loading-dots span:nth-child(2) {
  animation-delay: 0.2s;
}
.loading-dots span:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes blink {
  0%, 80%, 100% { opacity: 0.3; }
  40% { opacity: 1; }
}

/* 评价卡片 */
.review-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 4px;
}
.review-card {
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 10px 12px;
  background-color: #fafafa;
}
.review-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.review-rating {
  color: #f7ba2a;
  font-weight: 600;
  font-size: 13px;
}
.review-source {
  margin-left: auto;
  font-size: 12px;
  color: #909399;
}
.review-content {
  font-size: 14px;
  line-height: 1.7;
  color: #303133;
  white-space: pre-wrap;
}

/* 航班卡片 */
.flight-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 4px;
}
.flight-card {
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 10px 14px;
  background-color: #f6f9ff;
}
.flight-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.flight-no {
  font-weight: 600;
  color: #409eff;
  font-size: 14px;
}
.flight-route {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.flight-arrow {
  color: #409eff;
}
.flight-time {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}

/* 酒店卡片 */
.hotel-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 4px;
}
.hotel-card {
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 10px 14px;
  background-color: #fff7f0;
}
.hotel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.hotel-name {
  font-weight: 600;
  color: #e6a23c;
  font-size: 14px;
}
.hotel-meta {
  display: flex;
  gap: 10px;
  margin-bottom: 4px;
  font-size: 12px;
  color: #909399;
}
.hotel-address {
  font-size: 13px;
  color: #303133;
}
.hotel-tel {
  margin-top: 2px;
  font-size: 12px;
  color: #909399;
}
</style>
