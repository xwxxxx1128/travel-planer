<template>
  <div class="route-planner-page">
    <aside class="side-panel">
      <div class="panel-header">
        <div>
          <div class="brand">Trip plan AI</div>
          <h1>地图选点 / 路线规划</h1>
          <p>输入景区或在地图上点选目的地，自动串联最短路线。</p>
        </div>
        <el-dropdown @command="handleUserCommand">
          <span class="user-menu">
            <el-icon><User /></el-icon>
            {{ userStore.userInfo?.username || '用户' }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人信息</el-dropdown-item>
              <el-dropdown-item command="chat">智能助手</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <div class="search-wrap">
        <el-input
          v-model="searchText"
          placeholder="输入景区、酒店、商圈等地点（支持模糊匹配，如'雪山'）"
          clearable
          @input="onSearchInput"
          @keyup.enter="searchPlace"
          @focus="onSearchInput"
          @blur="hideSuggestions"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
          <template #append>
            <el-button type="primary" @click="searchPlace">搜索</el-button>
          </template>
        </el-input>
        <ul v-if="showSuggestions && searchSuggestions.length" class="suggestions">
          <li
            v-for="(tip, i) in searchSuggestions"
            :key="i"
            @mousedown.prevent="selectSuggestion(tip)"
          >
            <div class="sug-name">{{ tip.name }}</div>
            <div class="sug-addr">{{ tip.district }} {{ tip.address }}</div>
          </li>
        </ul>
      </div>

      <div class="start-card">
        <div class="card-title-row">
          <span>起点</span>
          <el-switch v-model="useCurrentLocationAsStart" active-text="当前位置" inactive-text="手动输入" />
        </div>
        <div v-if="!useCurrentLocationAsStart" class="search-wrap">
          <el-input
            v-model="startPoint"
            placeholder="例如：北京南站、天安门、酒店前台"
            clearable
            @input="onStartInput"
            @focus="onStartInput"
            @blur="hideStartSuggestions"
          />
          <ul v-if="showStartSuggestions && startSuggestions.length" class="suggestions">
            <li
              v-for="(tip, i) in startSuggestions"
              :key="i"
              @mousedown.prevent="selectStartSuggestion(tip)"
            >
              <div class="sug-name">{{ tip.name }}</div>
              <div class="sug-addr">{{ tip.district }} {{ tip.address }}</div>
            </li>
          </ul>
        </div>
        <el-alert
          v-else
          type="info"
          :closable="false"
          show-icon
          title="将优先使用浏览器定位；失败时可手动输入起点。"
        />
      </div>

      <div class="start-card">
        <div class="card-title-row">
          <span>交通方式</span>
        </div>
        <el-radio-group v-model="transportMode">
          <el-radio-button label="smart">智能推荐</el-radio-button>
          <el-radio-button label="driving">驾车</el-radio-button>
          <el-radio-button label="walking">步行</el-radio-button>
          <el-radio-button label="transit">公共交通</el-radio-button>
        </el-radio-group>
      </div>

      <div class="start-card">
        <div class="card-title-row">
          <span>终点</span>
        </div>
        <div v-if="endPoint.name" class="end-point-display">
          <span>{{ endPoint.name }}</span>
          <span class="end-point-coords">{{ endPoint.lng?.toFixed(4) }}, {{ endPoint.lat?.toFixed(4) }}</span>
          <el-button text type="danger" size="small" @click="clearEndPoint">清除</el-button>
        </div>
        <div v-else class="search-wrap">
          <el-input
            v-model="endSearchText"
            placeholder="输入终点（如：首都机场 / 故宫 / 某酒店），支持智能匹配"
            clearable
            @input="onEndInput"
            @focus="onEndInput"
            @blur="hideEndSuggestions"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <ul v-if="showEndSuggestions && endSuggestions.length" class="suggestions">
            <li
              v-for="(tip, i) in endSuggestions"
              :key="i"
              @mousedown.prevent="selectEndSuggestion(tip)"
            >
              <div class="sug-name">{{ tip.name }}</div>
              <div class="sug-addr">{{ tip.district }} {{ tip.address }}</div>
            </li>
          </ul>
          <div class="hint">不填则智能规划最优路线（按目的地顺序自动串联）</div>
        </div>
      </div>

      <div class="dest-head">
        <h2>已选目的地</h2>
        <el-button text type="danger" :disabled="destinations.length === 0" @click="clearDestinations">清空</el-button>
      </div>

      <div v-if="destinations.length === 0" class="empty-state">
        <el-icon><MapLocation /></el-icon>
        <p>搜索地点后可点击加入路线，或直接点击地图添加。</p>
      </div>

      <div v-else class="dest-list">
        <div v-for="(dest, index) in destinations" :key="dest.id" class="dest-item">
          <div class="dest-index">{{ index + 1 }}</div>
          <div class="dest-info">
            <div class="dest-name">{{ dest.name }}</div>
            <div class="dest-address">{{ dest.address || dest.location }}</div>
          </div>
          <el-button link type="danger" @click="removeDestination(dest.id)">删除</el-button>
        </div>
      </div>

      <div class="action-row">
        <el-button type="primary" :loading="loading" :disabled="destinations.length < 2" @click="planRoute">
          规划路线
        </el-button>
        <el-button :loading="locating" @click="locateCurrentPosition">定位当前位置</el-button>
      </div>

      <el-card v-if="routeResult" class="result-card" shadow="never">
        <template #header>路线规划结果</template>
        <div class="route-summary">
          <span>{{ routeResult.summary }}</span>
        </div>
        <div class="route-meta">
          <span>总距离：{{ routeResult.total_distance_text }}</span>
          <span>总耗时：{{ routeResult.total_duration_text }}</span>
          <span>建议方式：{{ routeResult.recommended_mode_label }}</span>
        </div>
        <div class="optimal-order" v-if="routeResult.optimal_order?.length">
          <strong>最优顺序：</strong><span>{{ routeResult.optimal_order.join(' → ') }}</span>
        </div>
        <div v-for="(segment, index) in routeResult.segments" :key="index" class="segment-item">
          <div class="segment-header">
            <strong>{{ index + 1 }}.</strong>
            <span>{{ segment.from }} → {{ segment.to }}</span>
            <span class="segment-meta">（{{ segment.distance_text }} · {{ segment.duration_text }} · {{ segment.transport_mode_label }}）</span>
          </div>
          <div v-if="segment.transit_steps && segment.transit_steps.length > 0" class="transit-steps">
            <div v-for="(step, si) in segment.transit_steps" :key="si" class="transit-step">
              <span class="step-badge" :class="step.line_kind === '地铁' ? 'badge-metro' : 'badge-bus'">{{ step.line_kind || '公交' }} · {{ step.line_name }}</span>
              <span class="step-desc">{{ step.departure?.stop || step.departure?.name }} → {{ step.arrival?.stop || step.arrival?.name }}</span>
            </div>
          </div>
        </div>
      </el-card>
    </aside>

    <main class="map-shell">
      <div ref="mapContainer" class="map-container"></div>
      <div class="map-tip">点击地图即可加入一个目的地；也可以先搜索后加入。</div>
    </main>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown, MapLocation, Search, User } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { configApi } from '@/api/config'

const router = useRouter()
const userStore = useUserStore()

const searchText = ref('')
const startPoint = ref('')
const useCurrentLocationAsStart = ref(true)
const transportMode = ref('smart')
const endPoint = ref({ name: '', lat: null, lng: null })
const startPointCoord = ref(null)
const startSuggestions = ref([])
const showStartSuggestions = ref(false)
let startTimer = null
const loading = ref(false)
const locating = ref(false)
const routeResult = ref(null)
const destinations = ref([])
const mapContainer = ref(null)
const runtimeConfig = ref({ amap_js_key: '' })
const searchSuggestions = ref([])
const showSuggestions = ref(false)
const searchLoading = ref(false)
let searchTimer = null
let currentCity = ''

let mapInstance = null
let markers = []
let polyline = null
let currentLocationPoint = null
let segmentPolylines = []
let routeEndpointMarkers = []

const amapJsKey = ref((import.meta.env.VITE_AMAP_JS_API_KEY || import.meta.env.VITE_AMAP_KEY || '').trim())

// 后端返回的 amap_js_key 已脱敏（如 6cb0****e07），不可作为真实 Key 使用
const isMasked = (v) => !v || /[*]{2,}/.test(v)

const currentAmapKey = () => amapJsKey.value.trim() || (isMasked(runtimeConfig.value.amap_js_key) ? '' : runtimeConfig.value.amap_js_key?.trim()) || ''

const loadRuntimeConfig = async () => {
  try {
    const config = await configApi.getRuntimeConfig()
    runtimeConfig.value = config || {}
    // 仅当构建期未注入、且运行时返回的是真实 Key（非脱敏）时才采用
    if (!amapJsKey.value && config?.amap_js_key && !isMasked(config.amap_js_key)) {
      amapJsKey.value = config.amap_js_key.trim()
    }
  } catch (error) {
    console.warn('load runtime config failed', error)
  }
}

const loadAmapScript = () => new Promise((resolve, reject) => {
  if (window.AMap) {
    resolve(window.AMap)
    return
  }

  const key = currentAmapKey()
  if (!key) {
    reject(new Error('未配置高德 JS API Key'))
    return
  }

  const callbackName = '__initAmapRoutePlanner'
  window[callbackName] = () => resolve(window.AMap)

  const script = document.createElement('script')
  script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(key)}&plugin=AMap.Geolocation,AMap.Geocoder,AMap.AutoComplete,AMap.PlaceSearch&callback=${callbackName}`
  script.async = true
  script.onerror = () => reject(new Error('高德地图加载失败'))
  document.head.appendChild(script)
})

const clearOverlays = () => {
  if (mapInstance && markers.length) {
    markers.forEach((marker) => mapInstance.remove(marker))
  }
  markers = []
  if (polyline && mapInstance) mapInstance.remove(polyline)
  polyline = null
  if (segmentPolylines.length && mapInstance) {
    segmentPolylines.forEach((p) => mapInstance.remove(p))
  }
  segmentPolylines = []
  if (routeEndpointMarkers.length && mapInstance) {
    routeEndpointMarkers.forEach((m) => mapInstance.remove(m))
  }
  routeEndpointMarkers = []
}

// 创建样式化圆形标记（起点/终点/目的地编号）
const createStyledMarker = (point, label, color) => {
  if (!mapInstance || !window.AMap) return null
  return new window.AMap.Marker({
    position: [Number(point.lng), Number(point.lat)],
    anchor: 'center',
    zIndex: 120,
    title: point.name || label,
    content: `<div style="width:26px;height:26px;border-radius:50%;background:${color};color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;border:2px solid #fff;box-shadow:0 2px 6px rgba(15,23,42,.35);">${label}</div>`,
  })
}

const fitMapToPoints = () => {
  if (!mapInstance || !window.AMap) return
  const points = destinations.value.map((item) => [item.lng, item.lat])
  if (currentLocationPoint) points.unshift([currentLocationPoint.lng, currentLocationPoint.lat])
  if (points.length > 0) mapInstance.setFitView()
}

// 在地图上按照路线顺序把 起点 → 各目的地 → 终点 连接起来
const drawRouteLine = (segments, orderedPoints) => {
  if (!mapInstance || !window.AMap) return

  // 清理旧的路线覆盖物
  if (polyline) { mapInstance.remove(polyline); polyline = null }
  if (segmentPolylines.length) {
    segmentPolylines.forEach((p) => mapInstance.remove(p))
    segmentPolylines = []
  }
  if (routeEndpointMarkers.length) {
    routeEndpointMarkers.forEach((m) => mapInstance.remove(m))
    routeEndpointMarkers = []
  }
  if (markers.length) {
    markers.forEach((m) => mapInstance.remove(m))
    markers = []
  }

  const overlays = []

  // 已规划：使用后端返回的真实路径（segments）按路线顺序绘制
  if (segments && segments.length > 0) {
    segments.forEach((seg) => {
      if (seg.path && seg.path.length >= 2) {
        const isEstimate = seg.is_estimate
        const color = isEstimate
          ? '#f59e0b'
          : seg.transport_mode_label === '公共交通'
            ? '#67C23A'
            : '#409eff'
        const line = new window.AMap.Polyline({
          path: seg.path,
          strokeColor: color,
          strokeWeight: 5,
          strokeStyle: isEstimate ? 'dashed' : 'solid',
          showDir: true,
          lineJoin: 'round',
          lineCap: 'round',
        })
        mapInstance.add(line)
        segmentPolylines.push(line)
        overlays.push(line)
      }
    })

    // 按路线顺序标记：起点 / 各目的地(编号) / 终点
    let destIndex = 0
    const points = (orderedPoints && orderedPoints.length) ? orderedPoints : destinations.value
    points.forEach((pt, idx) => {
      const isLast = idx === points.length - 1
      const kind = pt.kind ||
        (orderedPoints && orderedPoints.length
          ? (idx === 0 ? 'start' : isLast ? 'end' : 'destination')
          : 'destination')
      if (kind === 'start') {
        const m = createStyledMarker(pt, '起', '#22c55e')
        if (m) { mapInstance.add(m); routeEndpointMarkers.push(m); overlays.push(m) }
      } else if (kind === 'end') {
        const m = createStyledMarker(pt, '终', '#ef4444')
        if (m) { mapInstance.add(m); routeEndpointMarkers.push(m); overlays.push(m) }
      } else {
        destIndex += 1
        const m = createStyledMarker(pt, String(destIndex), '#409eff')
        if (m) { mapInstance.add(m); markers.push(m); overlays.push(m) }
      }
    })

    if (overlays.length > 0) mapInstance.setFitView(overlays, false, [40, 40, 40, 40])
    return
  }

  // 未规划（预览）：起点 + 目的地(加入顺序) + 终点 连成虚线
  const pts = []
  if (useCurrentLocationAsStart.value && currentLocationPoint) {
    pts.push({ name: '起点', lng: currentLocationPoint.lng, lat: currentLocationPoint.lat })
  } else if (startPointCoord.value) {
    pts.push({ name: '起点', lng: startPointCoord.value.lng, lat: startPointCoord.value.lat })
  }
  destinations.value.forEach((d) => pts.push({ name: d.name, lng: d.lng, lat: d.lat }))
  if (endPoint.value.lng != null) pts.push({ name: '终点', lng: endPoint.value.lng, lat: endPoint.value.lat })

  if (useCurrentLocationAsStart.value && currentLocationPoint) {
    const m = createStyledMarker({ name: '起点', lng: currentLocationPoint.lng, lat: currentLocationPoint.lat }, '起', '#22c55e')
    if (m) { mapInstance.add(m); routeEndpointMarkers.push(m); overlays.push(m) }
  } else if (startPointCoord.value) {
    const m = createStyledMarker({ name: '起点', lng: startPointCoord.value.lng, lat: startPointCoord.value.lat }, '起', '#22c55e')
    if (m) { mapInstance.add(m); routeEndpointMarkers.push(m); overlays.push(m) }
  }
  destinations.value.forEach((d, i) => {
    const m = createStyledMarker(d, String(i + 1), '#409eff')
    if (m) { mapInstance.add(m); markers.push(m); overlays.push(m) }
  })
  if (endPoint.value.lng != null) {
    const m = createStyledMarker({ name: '终点', lng: endPoint.value.lng, lat: endPoint.value.lat }, '终', '#ef4444')
    if (m) { mapInstance.add(m); routeEndpointMarkers.push(m); overlays.push(m) }
  }

  if (pts.length >= 2) {
    polyline = new window.AMap.Polyline({
      path: pts.map((p) => [Number(p.lng), Number(p.lat)]),
      strokeColor: '#909399',
      strokeWeight: 4,
      strokeStyle: 'dashed',
      showDir: true,
    })
    mapInstance.add(polyline)
  }
  if (overlays.length > 0) mapInstance.setFitView(overlays, false, [40, 40, 40, 40])
}

const addDestinationFromPoint = async (point, silent = false) => {
  const exists = destinations.value.some((item) => item.location === point.location)
  if (exists) {
    if (!silent) ElMessage.warning('该地点已添加')
    return
  }

  const dest = {
    id: `${point.location}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    name: point.name,
    location: point.location,
    lng: point.lng,
    lat: point.lat,
    address: point.address || point.name,
    source: point.source || 'map',
  }

  destinations.value.push(dest)
  drawRouteLine()
  routeResult.value = null
  if (!silent) ElMessage.success(`已添加：${dest.name}`)
}

const handleMapClick = (event) => {
  const lng = event.lnglat.getLng()
  const lat = event.lnglat.getLat()

  // 取离落点“坐标”最近的地点（不再限定景点类型，建筑/酒店/商圈等都参与），更贴近鼠标真实落点
  nearbyPoi(lng, lat, { radius: 1000, types: '', limit: 10 })
    .then((data) => {
      const pois = data?.pois || []
      let nearest = null
      let nearestDist = Infinity
      for (const p of pois) {
        const [plng, plat] = String(p.location).split(',').map(Number)
        if (isNaN(plng) || isNaN(plat)) continue
        const d = haversineMeters(lng, lat, plng, plat)
        if (d < nearestDist) {
          nearestDist = d
          nearest = p
        }
      }
      if (nearest && nearestDist <= 1000) {
        const [plng, plat] = String(nearest.location).split(',').map(Number)
        addDestinationFromPoint({
          name: nearest.name,
          location: nearest.location,
          lng: plng,
          lat: plat,
          address: nearest.address || nearest.name,
          source: 'map',
        }, true)
        return
      }
      // 兜底：用逆地理编码的地址名
      reverseGeocode(lng, lat).then((geo) => {
        addDestinationFromPoint({
          name: geo?.name || geo?.address || '选定位置',
          location: `${lng},${lat}`,
          lng,
          lat,
          address: geo?.address || `${lng.toFixed(6)}, ${lat.toFixed(6)}`,
          source: 'map',
        }, true)
      }).catch(() => {
        addDestinationFromPoint({ name: '选定位置', location: `${lng},${lat}`, lng, lat, address: `${lng.toFixed(6)}, ${lat.toFixed(6)}` }, true)
      })
    })
    .catch(() => {
      addDestinationFromPoint({ name: '选定位置', location: `${lng},${lat}`, lng, lat, address: `${lng.toFixed(6)}, ${lat.toFixed(6)}` }, true)
    })
}

const reverseGeocode = async (lng, lat) => {
  const response = await fetch('/api/reverse-geocode/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${userStore.token}` },
    body: JSON.stringify({ lng, lat }),
  })
  if (!response.ok) throw new Error('reverse geocode failed')
  return response.json()
}

const haversineMeters = (lng1, lat1, lng2, lat2) => {
  const R = 6371000
  const toRad = (d) => (d * Math.PI) / 180
  const dLat = toRad(lat2 - lat1)
  const dLng = toRad(lng2 - lng1)
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

const geocode = async (address) => {
  const response = await fetch('/api/geocode/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${userStore.token}` },
    body: JSON.stringify({ address }),
  })
  if (!response.ok) throw new Error('geocode failed')
  return response.json()
}

const fetchInputTips = async (keywords) => {
  const response = await fetch('/api/inputtips/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${userStore.token}` },
    body: JSON.stringify({ keywords, city: currentCity }),
  })
  if (!response.ok) throw new Error('inputtips failed')
  return response.json()
}

const nearbyPoi = async (lng, lat, options = {}) => {
  const response = await fetch('/api/nearby-poi/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${userStore.token}` },
    body: JSON.stringify({
      location: `${lng},${lat}`,
      radius: options.radius ?? 1000,
      types: options.types || '',
      limit: options.limit ?? 5,
    }),
  })
  if (!response.ok) throw new Error('nearby poi failed')
  return response.json()
}

const onSearchInput = () => {
  const kw = searchText.value.trim()
  if (searchTimer) clearTimeout(searchTimer)
  if (!kw) {
    searchSuggestions.value = []
    showSuggestions.value = false
    return
  }
  searchTimer = setTimeout(async () => {
    searchLoading.value = true
    try {
      const data = await fetchInputTips(kw)
      if (data?.success && Array.isArray(data.tips)) {
        searchSuggestions.value = data.tips.slice(0, 8)
        showSuggestions.value = true
      } else {
        searchSuggestions.value = []
        showSuggestions.value = false
      }
    } catch (e) {
      searchSuggestions.value = []
      showSuggestions.value = false
    } finally {
      searchLoading.value = false
    }
  }, 350)
}

const hideSuggestions = () => {
  setTimeout(() => { showSuggestions.value = false }, 150)
}

const onStartInput = () => {
  startPointCoord.value = null
  const kw = startPoint.value.trim()
  if (startTimer) clearTimeout(startTimer)
  if (!kw) {
    startSuggestions.value = []
    showStartSuggestions.value = false
    return
  }
  startTimer = setTimeout(async () => {
    try {
      const data = await fetchInputTips(kw)
      if (data?.success && Array.isArray(data.tips)) {
        startSuggestions.value = data.tips.filter((t) => t.location && t.location !== '[]').slice(0, 8)
        showStartSuggestions.value = true
      } else {
        startSuggestions.value = []
        showStartSuggestions.value = false
      }
    } catch (e) {
      startSuggestions.value = []
      showStartSuggestions.value = false
    }
  }, 350)
}

const hideStartSuggestions = () => {
  setTimeout(() => { showStartSuggestions.value = false }, 150)
}

const selectStartSuggestion = (tip) => {
  const [lng, lat] = String(tip.location).split(',').map(Number)
  startPoint.value = tip.name
  startPointCoord.value = {
    name: tip.name,
    lng,
    lat,
    location: tip.location,
  }
  startSuggestions.value = []
  showStartSuggestions.value = false
}

// 终点文字搜索：复用高德 inputtips 实现智能匹配推荐
const endSearchText = ref('')
const endSuggestions = ref([])
const showEndSuggestions = ref(false)
let endTimer = null

const onEndInput = () => {
  const kw = endSearchText.value.trim()
  if (endTimer) clearTimeout(endTimer)
  if (!kw) {
    endSuggestions.value = []
    showEndSuggestions.value = false
    return
  }
  endTimer = setTimeout(async () => {
    try {
      const data = await fetchInputTips(kw)
      if (data?.success && Array.isArray(data.tips)) {
        endSuggestions.value = data.tips
          .filter((t) => t.location && t.location !== '[]')
          .slice(0, 8)
        showEndSuggestions.value = true
      } else {
        endSuggestions.value = []
        showEndSuggestions.value = false
      }
    } catch (e) {
      endSuggestions.value = []
      showEndSuggestions.value = false
    }
  }, 350)
}

const hideEndSuggestions = () => {
  setTimeout(() => {
    showEndSuggestions.value = false
  }, 150)
}

const selectEndSuggestion = (tip) => {
  const [lng, lat] = String(tip.location).split(',').map(Number)
  endPoint.value = {
    name: tip.name,
    lng,
    lat,
    location: tip.location,
    address: `${tip.district || ''} ${tip.address || ''}`.trim() || tip.name,
  }
  endSearchText.value = ''
  endSuggestions.value = []
  showEndSuggestions.value = false
}

const selectSuggestion = (tip) => {
  const [lng, lat] = String(tip.location).split(',').map(Number)
  addDestinationFromPoint({
    name: tip.name,
    location: tip.location,
    lng,
    lat,
    address: `${tip.district || ''} ${tip.address || ''}`.trim() || tip.name,
    source: 'search',
  })
  searchText.value = ''
  searchSuggestions.value = []
  showSuggestions.value = false
}

const searchPlace = async () => {
  const query = searchText.value.trim()
  if (!query) {
    ElMessage.warning('请输入地点名称')
    return
  }

  // 优先使用智能提示的第一个结果（模糊匹配，例如输入'雪山'可匹配'雪山彩虹谷'）
  if (searchSuggestions.value.length) {
    selectSuggestion(searchSuggestions.value[0])
    return
  }

  try {
    const data = await geocode(query)
    if (data?.location) {
      const [lng, lat] = String(data.location).split(',').map(Number)
      await addDestinationFromPoint({
        name: data.name || query,
        location: data.location,
        lng,
        lat,
        address: data.address || data.name || query,
        source: 'search',
      })
      searchText.value = ''
    } else {
      ElMessage.warning('未找到匹配地点')
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('搜索失败，请稍后重试')
  }
}

const locateCurrentPosition = async () => {
  locating.value = true
  try {
    await loadAmapScript()
    await new Promise((resolve, reject) => {
      if (!window.AMap?.Geolocation) {
        reject(new Error('未加载定位插件'))
        return
      }
      const geolocation = new window.AMap.Geolocation({
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
        convert: true,
      })
      geolocation.getCurrentPosition((status, result) => {
        if (status === 'complete' && result.position) {
          resolve(result)
          return
        }
        reject(new Error(result?.message || '定位失败'))
      })
    }).then(async (result) => {
      const lng = result.position.getLng()
      const lat = result.position.getLat()
      currentLocationPoint = {
        name: '当前位置',
        location: `${lng},${lat}`,
        lng,
        lat,
        address: '当前位置',
      }
      if (mapInstance) mapInstance.setCenter([lng, lat])
      drawRouteLine()
      if (useCurrentLocationAsStart.value) startPoint.value = '当前位置'
      try {
        const geo = await reverseGeocode(lng, lat)
        if (geo?.address) {
          currentLocationPoint.address = geo.address
          if (useCurrentLocationAsStart.value) startPoint.value = geo.address
          if (geo?.adcode) currentCity = geo.adcode
        }
      } catch (error) {
        console.warn('reverse geocode failed', error)
      }
    })
    ElMessage.success('已获取当前位置')
  } catch (error) {
    console.error(error)
    ElMessage.warning('定位失败，请检查浏览器位置权限，或改用手动输入起点')
  } finally {
    locating.value = false
  }
}

const planRoute = async () => {
  if (destinations.value.length < 2) {
    ElMessage.warning('请至少选择两个目的地')
    return
  }

  loading.value = true
  try {
    // 确定起点坐标
    let startPointPayload = null
    if (useCurrentLocationAsStart.value && currentLocationPoint) {
      startPointPayload = {
        name: currentLocationPoint.name,
        lng: currentLocationPoint.lng,
        lat: currentLocationPoint.lat,
        location: currentLocationPoint.location,
      }
    } else if (startPointCoord.value) {
      startPointPayload = {
        name: startPointCoord.value.name,
        lng: startPointCoord.value.lng,
        lat: startPointCoord.value.lat,
        location: startPointCoord.value.location,
      }
    } else if (startPoint.value.trim()) {
      startPointPayload = startPoint.value.trim()
    }

    // 确定终点坐标
    let endPointPayload = null
    if (endPoint.value.lng != null) {
      endPointPayload = {
        name: endPoint.value.name,
        lng: endPoint.value.lng,
        lat: endPoint.value.lat,
        location: `${endPoint.value.lng},${endPoint.value.lat}`,
      }
    }

    // 构建 destination 列表
    const destinationPayloads = destinations.value.map((d) => ({
      name: d.name,
      lng: d.lng,
      lat: d.lat,
      location: d.location,
    }))

    // 调用后端真实接口
    const response = await fetch('/api/plan-route/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${userStore.token}`,
      },
      body: JSON.stringify({
        destinations: destinationPayloads,
        start_point: startPointPayload,
        end_point: endPointPayload,
        transport_mode: transportMode.value,
      }),
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.detail || `后端返回 ${response.status}`)
    }
    const result = await response.json()

    // 构建前端展示结构
    const segments = (result.segments || []).map((seg) => ({
      from: seg.from,
      to: seg.to,
      distance_text: seg.distance_km !== undefined ? `${seg.distance_km}公里` : '—',
      duration_text: seg.duration_minutes !== undefined ? `${seg.duration_minutes}分钟` : '—',
      transport_mode_label: seg.transport_mode_label || '驾车',
      path: seg.path || [],
      transit_steps: seg.transit_steps || [],
      is_estimate: !!seg.is_estimate,
    }))

    // 生成摘要
    const modeLabel = result.transport_mode_label || (transportMode.value === 'transit' ? '公交' : transportMode.value === 'driving' ? '驾车' : '步行')
    const orderText = result.optimal_order?.join(' → ') || ''
    const summary = transportMode.value === 'transit'
      ? `公共交通路线 · ${result.total_distance} · 约 ${result.total_time} · ${orderText}`
      : `${modeLabel}路线 · ${result.total_distance} · 约 ${result.total_time} · ${orderText}`

    routeResult.value = {
      total_distance_text: result.total_distance || '—',
      total_duration_text: result.total_time || '—',
      recommended_mode_label: result.transport_mode_label || modeLabel,
      optimal_order: result.optimal_order || [],
      summary,
      segments,
    }

    // 在地图上按路线顺序把各目的地连接起来
    drawRouteLine(segments, result.ordered_points)
    ElMessage.success(result.end_point ? '已规划固定终点路线' : '已规划最优路线')
  } catch (error) {
    console.error(error)
    ElMessage.error(error.message || '路线规划失败')
  } finally {
    loading.value = false
  }
}

const clearDestinations = () => {
  destinations.value = []
  routeResult.value = null
  drawRouteLine()
  clearOverlays()
}

const removeDestination = (id) => {
  destinations.value = destinations.value.filter((item) => item.id !== id)
  routeResult.value = null
  drawRouteLine()
}

const clearEndPoint = () => {
  endPoint.value = { name: '', lat: null, lng: null }
}

const handleUserCommand = (command) => {
  if (command === 'logout') {
    userStore.logout()
    router.push('/login')
  } else if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'chat') {
    router.push('/chat')
  }
}

const initMap = async () => {
  try {
    await loadRuntimeConfig()
    await loadAmapScript()
    mapInstance = new window.AMap.Map(mapContainer.value, {
      zoom: 11,
      center: [116.4074, 39.9042],
      viewMode: '2D',
    })
    mapInstance.on('click', handleMapClick)
  } catch (error) {
    console.error('地图初始化失败', error)
    ElMessage.error(error?.message || '地图加载失败，请检查高德 JS Key')
  }
}

onMounted(async () => {
  await nextTick()
  await initMap()
})

onBeforeUnmount(() => {
  if (mapInstance) {
    mapInstance.destroy()
    mapInstance = null
  }
})
</script>

<style scoped>
.route-planner-page {
  display: grid;
  grid-template-columns: 380px 1fr;
  min-height: 100vh;
  background: #f5f7fb;
}
.side-panel {
  padding: 24px;
  background: #fff;
  border-right: 1px solid #e5e7eb;
  overflow-y: auto;
}
.panel-header, .card-title-row, .dest-head, .route-summary, .segment-item, .action-row, .user-menu {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.brand { display:inline-flex; padding:6px 10px; border-radius:999px; background:#e8f2ff; color:#409eff; font-weight:700; margin-bottom:8px; }
h1 { margin: 0 0 8px; font-size: 26px; }
p { margin: 0; color: #64748b; line-height: 1.7; }
.start-card, .result-card { margin-top: 18px; }
.dest-list { display: grid; gap: 10px; margin-top: 12px; }
.dest-item { display: grid; grid-template-columns: 28px 1fr auto; gap: 10px; align-items: center; padding: 10px 12px; background: #f8fafc; border-radius: 12px; }
.dest-index { width: 28px; height: 28px; border-radius: 50%; background: #409eff; color: #fff; display:grid; place-items:center; font-size: 12px; }
.dest-name { font-weight: 600; }
.dest-address { font-size: 12px; color: #64748b; margin-top: 2px; }
.action-row { margin-top: 18px; align-items: stretch; flex-wrap: wrap; }
.action-row .el-button { flex: 1; }
.empty-state { margin-top: 16px; padding: 24px; text-align:center; color:#64748b; border:1px dashed #dbe3ef; border-radius:16px; }
.empty-state .el-icon { font-size: 28px; margin-bottom: 8px; color:#409eff; }
.result-card :deep(.el-card__body) { display: grid; gap: 10px; }
.route-summary { flex-wrap: wrap; font-size: 13px; color: #334155; font-weight: 500; }
.route-meta { display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: #64748b; margin-top: 4px; }
.optimal-order { font-size: 12px; color: #64748b; margin-top: 4px; }
.segment-item { display: flex; flex-direction: column; gap: 6px; font-size: 13px; padding-top: 10px; border-top: 1px solid #eef2f7; }
.segment-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.segment-meta { font-size: 12px; color: #64748b; }
.end-point-display { display: flex; align-items: center; gap: 8px; background: #f8fafc; padding: 8px 12px; border-radius: 8px; margin-top: 8px; }
.end-point-coords { font-size: 11px; color: #94a3b8; }
.transit-steps { margin-left: 20px; padding: 6px 0; }
.transit-step { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; }
.step-badge { color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; white-space: nowrap; }
.badge-bus { background: #409eff; }
.badge-metro { background: #f59e0b; }
.step-desc { color: #334155; }
.search-wrap { position: relative; }
.hint { font-size: 12px; color: #94a3b8; margin-top: 6px; line-height: 1.5; }
.suggestions {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 20;
  margin: 0;
  padding: 4px;
  list-style: none;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
  max-height: 280px;
  overflow-y: auto;
}
.suggestions li { padding: 8px 10px; border-radius: 8px; cursor: pointer; }
.suggestions li:hover { background: #f1f5f9; }
.sug-name { font-size: 13px; font-weight: 600; color: #1e293b; }
.sug-addr { font-size: 11px; color: #94a3b8; margin-top: 2px; }
.map-shell { display: grid; grid-template-rows: 1fr auto; min-height: 100vh; }
.map-container { min-height: 0; }
.map-tip { padding: 10px 16px; background: rgba(255,255,255,0.92); border-top: 1px solid #e5e7eb; color:#64748b; }
@media (max-width: 960px) {
  .route-planner-page { grid-template-columns: 1fr; }
  .side-panel { border-right: none; border-bottom: 1px solid #e5e7eb; }
}
</style>
