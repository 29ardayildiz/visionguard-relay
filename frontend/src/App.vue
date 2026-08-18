<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import AppToast from './components/AppToast.vue'
import InstallPrompt from './components/InstallPrompt.vue'

// Native push/pop hissi: hiyerarşide ileri giderken (login -> viewer -> admin)
// sağdan-içeri, geri dönerken soldan-içeri kaydırma. Derinlik haritası route
// sayısı kadar küçük olduğu için ayrı bir meta alanına gerek yok.
const ROUTE_DEPTH: Record<string, number> = { login: 0, viewer: 1, admin: 2 }

const router = useRouter()
const transitionName = ref('page')

router.afterEach((to, from) => {
  const toDepth = ROUTE_DEPTH[String(to.name)] ?? 0
  const fromDepth = ROUTE_DEPTH[String(from.name)] ?? 0
  transitionName.value = toDepth >= fromDepth ? 'page' : 'page-back'
})
</script>

<template>
  <RouterView v-slot="{ Component }">
    <Transition mode="out-in" :name="transitionName">
      <component :is="Component" />
    </Transition>
  </RouterView>
  <AppToast />
  <InstallPrompt />
</template>
