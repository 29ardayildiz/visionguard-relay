import { createRouter, createWebHistory } from 'vue-router'

import LoginView from '../views/LoginView.vue'
import ViewerView from '../views/ViewerView.vue'
import AdminView from '../views/AdminView.vue'
import { isAuthenticated } from '../lib/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', component: LoginView },
    { path: '/', name: 'viewer', component: ViewerView, meta: { requiresAuth: true } },
    { path: '/admin', name: 'admin', component: AdminView, meta: { requiresAuth: true } },
  ],
})

// Auth kontrolü ROUTER seviyesinde, render'dan ÖNCE: eski onMounted-guard
// yaklaşımı korumalı ekranı önce çizip ~1sn sonra login'e fırlatıyordu
// (özellikle iOS standalone ilk açılışında rahatsız edici bir flaş).
// Async guard, navigasyonu /health cevabına kadar bekletir — oturum yoksa
// ilk boyanan ekran doğrudan login olur.
router.beforeEach(async (to) => {
  if (to.meta.requiresAuth) {
    if (await isAuthenticated()) return true
    return { name: 'login', replace: true }
  }
  if (to.name === 'login' && (await isAuthenticated())) {
    // Oturumu olan kullanıcı login'e düşmesin — doğrudan viewer.
    return { name: 'viewer', replace: true }
  }
  return true
})

export default router
