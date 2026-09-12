import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const refreshToken = ref(localStorage.getItem('refreshToken') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || 'null'))
  const isLoggedIn = computed(() => !!token.value)

  const setTokens = (tokenValue, refreshValue) => {
    token.value = tokenValue || ''
    if (tokenValue) localStorage.setItem('token', tokenValue)
    else localStorage.removeItem('token')

    refreshToken.value = refreshValue || ''
    if (refreshValue) localStorage.setItem('refreshToken', refreshValue)
    else localStorage.removeItem('refreshToken')
  }

  const login = (tokenValue, refreshValue, userValue) => {
    setTokens(tokenValue, refreshValue)
    userInfo.value = userValue
    localStorage.setItem('userInfo', JSON.stringify(userValue))
  }

  const logout = () => {
    setTokens('', '')
    userInfo.value = null
    localStorage.removeItem('userInfo')
  }

  return { token, refreshToken, userInfo, isLoggedIn, login, logout, setTokens }
})
