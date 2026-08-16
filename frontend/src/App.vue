<script setup lang="ts">
import AppToast from './components/AppToast.vue'
import InstallPrompt from './components/InstallPrompt.vue'
</script>

<template>
  <RouterView v-slot="{ Component }">
    <Transition mode="out-in" name="page">
      <component :is="Component" />
    </Transition>
  </RouterView>
  <AppToast />
  <InstallPrompt />
</template>
