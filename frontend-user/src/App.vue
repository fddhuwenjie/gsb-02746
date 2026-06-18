<template>
  <div class="min-h-screen bg-grid relative flex flex-col">
    <div class="bg-glow"></div>
    
    <!-- 顶部导航 -->
    <nav class="glass-light sticky top-0 z-50 border-b border-white/5">
      <div class="max-w-7xl mx-auto px-6 lg:px-8">
        <div class="flex justify-between h-20">
          <router-link to="/" class="flex items-center gap-4 group">
            <div class="relative">
              <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-purple-500/25 group-hover:shadow-purple-500/40 transition-shadow">
                <span class="text-white font-bold text-xl">R</span>
              </div>
              <div class="absolute -inset-1 rounded-2xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 opacity-0 group-hover:opacity-30 blur-lg transition-opacity"></div>
            </div>
            <div>
              <h1 class="font-serif text-xl font-semibold text-white">RCQ读者书库</h1>
              <p class="text-xs text-zinc-500">Reader's Collection Quest</p>
            </div>
          </router-link>
          
          <div class="flex items-center gap-2">
            <router-link 
              v-for="item in navItems" 
              :key="item.path" 
              :to="item.path"
              class="relative px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-300"
              :class="$route.path === item.path 
                ? 'text-white bg-white/10' 
                : 'text-zinc-400 hover:text-white hover:bg-white/5'"
            >
              <span class="relative z-10 flex items-center gap-2">
                <component :is="item.icon" class="w-4 h-4" />
                {{ item.name }}
              </span>
              <div v-if="$route.path === item.path" class="absolute inset-0 rounded-xl bg-gradient-to-r from-indigo-500/20 to-purple-500/20 border border-indigo-500/30"></div>
            </router-link>
          </div>
        </div>
      </div>
    </nav>

    <!-- 主内容 -->
    <main class="flex-1 max-w-7xl mx-auto px-6 lg:px-8 py-10 w-full">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <!-- 底部 -->
    <footer class="border-t border-white/5 mt-auto">
      <div class="max-w-7xl mx-auto px-6 lg:px-8 py-8">
        <p class="text-center text-zinc-600 text-sm">
          © 2024 RCQ读者书库 · 优雅阅读，品味生活
        </p>
      </div>
    </footer>

    <!-- 全局 Toast -->
    <Toast 
      v-model="toastState.visible"
      :message="toastState.message"
      :type="toastState.type"
      :duration="toastState.duration"
    />
  </div>
</template>

<script setup>
import { h } from 'vue'
import Toast from './components/Toast.vue'
import { useToast } from './composables/useToast'

const { toastState } = useToast()

const IconBook = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-4 h-4' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253' })]) }
const IconDownload = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-4 h-4' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4' })]) }
const IconSettings = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-4 h-4' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z' }), h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M15 12a3 3 0 11-6 0 3 3 0 016 0z' })]) }

const navItems = [
  { path: '/', name: '书库', icon: IconBook },
  { path: '/crawler', name: '抓取', icon: IconDownload },
  { path: '/settings', name: '设置', icon: IconSettings }
]
</script>
