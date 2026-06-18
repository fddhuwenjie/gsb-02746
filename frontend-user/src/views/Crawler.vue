<template>
  <div class="max-w-3xl mx-auto">
    <!-- 页面标题 -->
    <div class="mb-10">
      <h2 class="text-4xl font-serif font-bold gradient-text mb-3">抓取文章</h2>
      <p class="text-zinc-500">从配置的数据源抓取指定期数的文章</p>
    </div>

    <!-- 快捷操作 -->
    <div class="glass rounded-2xl p-6 mb-8">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-medium text-white flex items-center gap-2">
          <svg class="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
          </svg>
          快捷测试
        </h3>
        <span class="text-xs text-zinc-500">无需配置数据源即可验证功能</span>
      </div>
      <div class="flex gap-4">
        <button 
          @click="mockCrawl"
          :disabled="mockLoading"
          class="flex-1 py-4 px-6 rounded-xl bg-gradient-to-r from-green-500/20 to-emerald-500/20 border border-green-500/30 text-green-300 font-medium hover:from-green-500/30 hover:to-emerald-500/30 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
        >
          <svg v-if="mockLoading" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
          </svg>
          一键模拟抓取
        </button>
        <button 
          @click="seedTestData"
          :disabled="seedLoading"
          class="flex-1 py-4 px-6 rounded-xl bg-gradient-to-r from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 text-indigo-300 font-medium hover:from-indigo-500/30 hover:to-purple-500/30 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
        >
          <svg v-if="seedLoading" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
          </svg>
          添加测试数据
        </button>
      </div>
      <p class="mt-3 text-xs text-zinc-600 text-center">
        💡 点击上方按钮可快速添加模拟数据，用于验证文章列表、详情、筛选等功能
      </p>
    </div>

    <!-- 抓取表单 -->
    <div class="glass rounded-2xl p-8 mb-8">
      <form @submit.prevent="startCrawl" class="space-y-6">
        <!-- 年月选择 -->
        <div class="grid grid-cols-2 gap-6">
          <div>
            <label class="block text-sm font-medium text-zinc-300 mb-3">
              <span class="flex items-center gap-2">
                <svg class="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                </svg>
                年份 <span class="text-red-400">*</span>
              </span>
            </label>
            <select 
              v-model="form.year" 
              required
              class="w-full px-4 py-4 rounded-xl bg-white/5 border border-white/10 text-white focus:outline-none input-glow transition-all cursor-pointer"
            >
              <option v-for="y in yearOptions" :key="y" :value="y" class="bg-zinc-900">{{ y }}年</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-zinc-300 mb-3">
              <span class="flex items-center gap-2">
                <svg class="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                月份 <span class="text-red-400">*</span>
              </span>
            </label>
            <select 
              v-model="form.month" 
              required
              class="w-full px-4 py-4 rounded-xl bg-white/5 border border-white/10 text-white focus:outline-none input-glow transition-all cursor-pointer"
            >
              <option v-for="m in 12" :key="m" :value="m" class="bg-zinc-900">{{ m }}月</option>
            </select>
          </div>
        </div>

        <!-- 期数 -->
        <div>
          <label class="block text-sm font-medium text-zinc-300 mb-3">
            <span class="flex items-center gap-2">
              <svg class="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
              </svg>
              期数 (可选)
            </span>
          </label>
          <input 
            v-model="form.issue" 
            type="text" 
            maxlength="50"
            placeholder="如: 第1期、上半月刊"
            class="w-full px-4 py-4 rounded-xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none input-glow transition-all"
          >
        </div>

        <!-- 保存路径 -->
        <div>
          <label class="block text-sm font-medium text-zinc-300 mb-3">
            <span class="flex items-center gap-2">
              <svg class="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
              </svg>
              保存路径 (可选)
            </span>
          </label>
          <input 
            v-model="form.save_path" 
            type="text" 
            maxlength="200"
            placeholder="默认: ./data/articles"
            class="w-full px-4 py-4 rounded-xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none input-glow transition-all"
          >
          <p class="mt-2 text-xs text-zinc-600">文章将按 年份/月份/文章标题.txt 的结构保存</p>
        </div>

        <!-- 提交按钮 -->
        <button 
          type="submit" 
          :disabled="status.status === 'running'"
          class="w-full btn-glow py-4 px-6 rounded-xl text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
        >
          <svg v-if="status.status === 'running'" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
          </svg>
          {{ status.status === 'running' ? '正在抓取...' : '开始抓取' }}
        </button>
      </form>

      <!-- 状态显示 -->
      <div v-if="status.status !== 'idle'" class="mt-6">
        <div 
          class="p-5 rounded-xl flex items-center gap-4"
          :class="{
            'bg-indigo-500/10 border border-indigo-500/20': status.status === 'running',
            'bg-green-500/10 border border-green-500/20': status.status === 'completed',
            'bg-red-500/10 border border-red-500/20': status.status === 'error'
          }"
        >
          <div 
            class="w-10 h-10 rounded-full flex items-center justify-center"
            :class="{
              'bg-indigo-500/20': status.status === 'running',
              'bg-green-500/20': status.status === 'completed',
              'bg-red-500/20': status.status === 'error'
            }"
          >
            <svg v-if="status.status === 'running'" class="w-5 h-5 text-indigo-400 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <svg v-else-if="status.status === 'completed'" class="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
            </svg>
            <svg v-else class="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </div>
          <div class="flex-1">
            <p :class="{
              'text-indigo-300': status.status === 'running',
              'text-green-300': status.status === 'completed',
              'text-red-300': status.status === 'error'
            }">
              {{ status.message }}
            </p>
          </div>
          <div v-if="status.articles_count > 0" class="text-right">
            <p class="text-2xl font-bold text-white">{{ status.articles_count }}</p>
            <p class="text-xs text-zinc-500">篇文章</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 数据源配置 -->
    <div class="glass rounded-2xl p-8">
      <div class="flex items-center justify-between mb-6">
        <h3 class="text-lg font-medium text-white flex items-center gap-2">
          <svg class="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"/>
          </svg>
          数据源配置
        </h3>
        <router-link to="/settings" class="text-sm text-indigo-400 hover:text-indigo-300 transition-colors">
          管理数据源 →
        </router-link>
      </div>

      <div v-if="sources.length" class="space-y-3">
        <div 
          v-for="s in sources" 
          :key="s.name" 
          class="p-4 rounded-xl bg-white/5 border border-white/5 hover:border-indigo-500/30 transition-colors"
        >
          <div class="flex items-center justify-between">
            <div>
              <p class="font-medium text-white">{{ s.name }}</p>
              <p class="text-sm text-zinc-500 mt-1">{{ s.base_url }}</p>
            </div>
            <div class="w-3 h-3 rounded-full bg-green-500 pulse"></div>
          </div>
        </div>
      </div>

      <div v-else class="text-center py-8">
        <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-yellow-500/10 flex items-center justify-center">
          <svg class="w-8 h-8 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
          </svg>
        </div>
        <p class="text-yellow-400 font-medium mb-2">提供网站地址</p>
        <p class="text-zinc-400 mb-2">暂无配置的数据源</p>
        <p class="text-sm text-zinc-600">请在设置页面添加数据源，或使用上方「一键模拟抓取」测试功能</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { crawlerApi, articleApi } from '../api'
import { useToast } from '../composables/useToast'

const { success, error } = useToast()

const currentYear = new Date().getFullYear()
const yearOptions = Array.from({ length: 10 }, (_, i) => currentYear - i)

const form = ref({
  year: currentYear,
  month: new Date().getMonth() + 1,
  issue: '',
  save_path: ''
})

const status = ref({ status: 'idle', message: '', articles_count: 0 })
const sources = ref([])
const mockLoading = ref(false)
const seedLoading = ref(false)
let pollInterval = null

const startCrawl = async () => {
  try {
    await crawlerApi.start(form.value)
    status.value = { status: 'running', message: '正在抓取文章...', articles_count: 0 }
    pollStatus()
  } catch (e) {
    const msg = e.response?.data?.detail || '启动失败，请检查数据源配置'
    status.value = { status: 'error', message: msg, articles_count: 0 }
    error(msg)
  }
}

const mockCrawl = async () => {
  mockLoading.value = true
  try {
    const { data } = await crawlerApi.mock()
    success(data.message || `模拟抓取成功，已添加 ${data.articles_count} 篇文章`)
    status.value = { status: 'completed', message: '模拟抓取完成', articles_count: data.articles_count }
  } catch (e) {
    const msg = e.response?.data?.detail || '模拟抓取失败'
    error(msg)
  } finally {
    mockLoading.value = false
  }
}

const seedTestData = async () => {
  seedLoading.value = true
  try {
    const { data } = await articleApi.seed()
    success(data.message || '测试数据已添加')
  } catch (e) {
    const msg = e.response?.data?.detail || '添加测试数据失败'
    error(msg)
  } finally {
    seedLoading.value = false
  }
}

const pollStatus = () => {
  pollInterval = setInterval(async () => {
    try {
      const { data } = await crawlerApi.getStatus()
      status.value = data
      if (data.status !== 'running') {
        clearInterval(pollInterval)
        if (data.status === 'completed') {
          success(`抓取完成，共 ${data.articles_count} 篇文章`)
        } else if (data.status === 'error') {
          error(data.message)
        }
      }
    } catch (e) {
      clearInterval(pollInterval)
    }
  }, 1000)
}

const loadSources = async () => {
  try {
    const { data } = await crawlerApi.getSources()
    sources.value = data.sources || []
  } catch (e) {
    console.error(e)
  }
}

onMounted(loadSources)
onUnmounted(() => clearInterval(pollInterval))
</script>
