<template>
  <div class="max-w-3xl mx-auto">
    <!-- 页面标题 -->
    <div class="mb-10">
      <h2 class="text-4xl font-serif font-bold gradient-text mb-3">系统设置</h2>
      <p class="text-zinc-500">配置数据源和存储路径</p>
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
        <span class="text-xs text-zinc-500">一键添加模拟配置</span>
      </div>
      <button 
        @click="addMockSource"
        :disabled="mockLoading"
        class="w-full py-4 px-6 rounded-xl bg-gradient-to-r from-green-500/20 to-emerald-500/20 border border-green-500/30 text-green-300 font-medium hover:from-green-500/30 hover:to-emerald-500/30 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
      >
        <svg v-if="mockLoading" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
        </svg>
        一键添加模拟数据源
      </button>
      <p class="mt-3 text-xs text-zinc-600 text-center">
        💡 添加模拟数据源后，可在抓取页面使用「一键模拟抓取」功能测试完整流程
      </p>
    </div>

    <!-- 基础设置 -->
    <div class="glass rounded-2xl p-8 mb-8">
      <h3 class="text-lg font-medium text-white mb-6 flex items-center gap-2">
        <svg class="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
        </svg>
        存储设置
      </h3>

      <div class="space-y-6">
        <div>
          <label class="block text-sm font-medium text-zinc-300 mb-3">文章保存路径</label>
          <input 
            v-model="settings.articles_path" 
            type="text"
            maxlength="200"
            class="w-full px-4 py-4 rounded-xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none input-glow transition-all"
          >
          <p class="mt-2 text-xs text-zinc-600">抓取的文章将保存到此目录（设置会持久化保存）</p>
        </div>

        <button 
          @click="saveSettings"
          :disabled="saveLoading"
          class="btn-glow px-6 py-3 rounded-xl text-white font-medium flex items-center gap-2 disabled:opacity-50"
        >
          <svg v-if="saveLoading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          保存设置
        </button>
      </div>
    </div>

    <!-- 添加数据源 -->
    <div class="glass rounded-2xl p-8 mb-8">
      <h3 class="text-lg font-medium text-white mb-6 flex items-center gap-2">
        <svg class="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
        </svg>
        添加数据源
      </h3>

      <form @submit.prevent="addSource" class="space-y-5">
        <div class="grid grid-cols-2 gap-5">
          <div>
            <label class="block text-sm font-medium text-zinc-300 mb-2">数据源名称 <span class="text-red-400">*</span></label>
            <input 
              v-model="newSource.name" 
              required
              maxlength="50"
              placeholder="如: 读者杂志"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none input-glow transition-all"
            >
          </div>
          <div>
            <label class="block text-sm font-medium text-zinc-300 mb-2">基础URL <span class="text-red-400">*</span></label>
            <input 
              v-model="newSource.base_url" 
              required
              placeholder="https://example.com"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none input-glow transition-all"
            >
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-zinc-300 mb-2">列表页URL模式 <span class="text-red-400">*</span></label>
          <input 
            v-model="newSource.list_pattern" 
            required
            placeholder="/{year}/{month}"
            class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none input-glow transition-all"
          >
          <p class="mt-2 text-xs text-zinc-600">支持变量: {year}, {month}, {issue}</p>
        </div>

        <div class="grid grid-cols-2 gap-5">
          <div>
            <label class="block text-sm font-medium text-zinc-300 mb-2">文章链接选择器 <span class="text-red-400">*</span></label>
            <input 
              v-model="newSource.article_selector" 
              required
              placeholder=".article-list a"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none input-glow transition-all"
            >
          </div>
          <div>
            <label class="block text-sm font-medium text-zinc-300 mb-2">标题选择器 <span class="text-red-400">*</span></label>
            <input 
              v-model="newSource.title_selector" 
              required
              placeholder="h1.title"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none input-glow transition-all"
            >
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-zinc-300 mb-2">内容选择器 <span class="text-red-400">*</span></label>
          <input 
            v-model="newSource.content_selector" 
            required
            placeholder=".article-content"
            class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none input-glow transition-all"
          >
        </div>

        <div class="grid grid-cols-2 gap-5">
          <div>
            <label class="block text-sm font-medium text-zinc-300 mb-2">作者选择器 (可选)</label>
            <input 
              v-model="newSource.author_selector" 
              placeholder=".author"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none input-glow transition-all"
            >
          </div>
          <div>
            <label class="block text-sm font-medium text-zinc-300 mb-2">分类选择器 (可选)</label>
            <input 
              v-model="newSource.category_selector" 
              placeholder=".category"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none input-glow transition-all"
            >
          </div>
        </div>

        <button 
          type="submit"
          :disabled="addLoading"
          class="w-full py-4 rounded-xl bg-white/5 border border-white/10 text-white font-medium hover:bg-white/10 hover:border-indigo-500/30 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
        >
          <svg v-if="addLoading" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
          </svg>
          添加数据源
        </button>
      </form>
    </div>

    <!-- 使用说明 -->
    <div class="glass rounded-2xl p-8">
      <h3 class="text-lg font-medium text-white mb-4 flex items-center gap-2">
        <svg class="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        配置说明
      </h3>
      <div class="prose prose-invert prose-sm max-w-none">
        <p class="text-zinc-400 leading-relaxed">
          数据源配置用于指定如何从目标网站抓取文章。您需要提供：
        </p>
        <ul class="text-zinc-500 space-y-2 mt-4">
          <li><span class="text-indigo-400">基础URL</span> - 目标网站的根地址（必须以 http:// 或 https:// 开头）</li>
          <li><span class="text-indigo-400">列表页模式</span> - 文章列表页的URL结构，支持年月变量</li>
          <li><span class="text-indigo-400">CSS选择器</span> - 用于定位页面中的文章链接、标题、内容等元素</li>
        </ul>
        <p class="text-zinc-500 mt-4">
          配置文件位于: <code class="px-2 py-1 rounded bg-white/5 text-indigo-300">backend/config/sources.json</code>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { settingsApi } from '../api'
import { useToast } from '../composables/useToast'

const { success, error } = useToast()

const settings = ref({ articles_path: '' })
const saveLoading = ref(false)
const addLoading = ref(false)
const mockLoading = ref(false)

const newSource = ref({
  name: '',
  base_url: '',
  list_pattern: '/{year}/{month}',
  article_selector: 'a',
  title_selector: 'h1',
  content_selector: '.content',
  author_selector: '',
  category_selector: ''
})

const loadSettings = async () => {
  try {
    const { data } = await settingsApi.get()
    settings.value = data
  } catch (e) {
    console.error(e)
  }
}

const saveSettings = async () => {
  saveLoading.value = true
  try {
    await settingsApi.update(settings.value)
    success('设置已保存')
  } catch (e) {
    const msg = e.response?.data?.detail || '保存失败'
    error(msg)
  } finally {
    saveLoading.value = false
  }
}

const addSource = async () => {
  addLoading.value = true
  try {
    await settingsApi.addSource(newSource.value)
    success('数据源已添加')
    newSource.value = {
      name: '',
      base_url: '',
      list_pattern: '/{year}/{month}',
      article_selector: 'a',
      title_selector: 'h1',
      content_selector: '.content',
      author_selector: '',
      category_selector: ''
    }
  } catch (e) {
    const msg = e.response?.data?.detail || '添加失败'
    error(msg)
  } finally {
    addLoading.value = false
  }
}

const addMockSource = async () => {
  mockLoading.value = true
  try {
    const { data } = await settingsApi.addMockSource()
    success(data.message || '模拟数据源已添加')
  } catch (e) {
    const msg = e.response?.data?.detail || '添加失败'
    error(msg)
  } finally {
    mockLoading.value = false
  }
}

onMounted(loadSettings)
</script>
