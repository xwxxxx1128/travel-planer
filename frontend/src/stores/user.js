import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || 'null'))
  const isLoggedIn = computed(() => !!token.value)

  const login = (tokenValue, userValue) => {
    token.value = tokenValue
    userInfo.value = userValue
    localStorage.setItem('token', tokenValue)
    localStorage.setItem('userInfo', JSON.stringify(userValue))
  }
  const logout = () => {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
  }
  return { token, userInfo, isLoggedIn, login, logout }
})
