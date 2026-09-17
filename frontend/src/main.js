import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import router from './router'
import App from './App.vue'

const app = createApp(App)
for (const [name, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, component)
}
app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.mount('#app')

// 构建版本哨兵：切回标签页 / 每分钟检查一次，一旦发现后端重新构建过就自动刷新，
// 免去"必须先手动刷新一次才能看到新增功能"的困扰。
let uiVersion = null
const checkUiVersion = async () => {
  try {
    const res = await fetch('/api/ui-version', { cache: 'no-store' })
    if (!res.ok) return
    const data = await res.json()
    const version = String(data.version || '')
    if (!version) return
    if (uiVersion === null) {
      uiVersion = version
      return
    }
    if (version !== uiVersion) window.location.reload()
  } catch (e) {
    // 网络异常时静默忽略，不影响正常使用
  }
}
checkUiVersion()
setInterval(checkUiVersion, 60 * 1000)
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) checkUiVersion()
})
