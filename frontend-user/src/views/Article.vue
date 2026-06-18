<template>
  <div class="max-w-4xl mx-auto">
    <!-- 返回按钮 -->
    <button 
      @click="$router.back()" 
      class="flex items-center gap-2 text-zinc-500 hover:text-white mb-8 transition-colors group"
    >
      <svg class="w-5 h-5 group-hover:-translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
      </svg>
      返回书库
    </button>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex flex-col items-center justify-center py-32">
      <div class="loader mb-4"></div>
      <p class="text-zinc-500">加载中...</p>
    </div>

    <!-- 文章内容 -->
    <article v-else-if="article" class="glass rounded-3xl overflow-hidden">
      <!-- 文章头部 -->
      <header class="relative p-10 pb-8 border-b border-white/5">
        <!-- 装饰背景 -->
        <div class="absolute inset-0 bg-gradient-to-br from-indigo-500/10 via-purple-500/5 to-transparent"></div>
        
        <div class="relative">
          <!-- 分类标签 -->
          <div v-if="article.category" class="mb-4">
            <span class="tag px-4 py-1.5 rounded-full text-sm text-indigo-300">
              {{ article.category }}
            </span>
          </div>

          <!-- 标题 -->
          <h1 class="font-serif text-4xl md:text-5xl font-bold text-white leading-tight mb-6">
            {{ article.title }}
          </h1>

          <!-- 元信息 -->
          <div class="flex flex-wrap items-center gap-6 text-zinc-400">
            <div v-if="article.author" class="flex items-center gap-2">
              <div class="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center">
                <span class="text-white font-medium">{{ article.author[0] }}</span>
              </div>
              <div>
                <p class="text-white font-medium">{{ article.author }}</p>
                <p class="text-xs text-zinc-500">作者</p>
              </div>
            </div>

            <div v-if="article.year && article.month" class="flex items-center gap-2">
              <div class="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center">
                <svg class="w-5 h-5 text-zinc-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                </svg>
              </div>
              <div>
                <p class="text-white">{{ article.year }}年{{ article.month }}月</p>
                <p class="text-xs text-zinc-500">发布时间</p>
              </div>
            </div>

            <div v-if="article.issue" class="flex items-center gap-2">
              <div class="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center">
                <svg class="w-5 h-5 text-zinc-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
                </svg>
              </div>
              <div>
                <p class="text-white">{{ article.issue }}</p>
                <p class="text-xs text-zinc-500">期数</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <!-- 文章正文 -->
      <div class="p-10">
        <div class="reading-content whitespace-pre-wrap">
          {{ article.content }}
        </div>
      </div>

      <!-- 文章底部 -->
      <footer class="p-10 pt-0">
        <div class="border-t border-white/5 pt-8">
          <div class="flex items-center justify-between">
            <div class="text-sm text-zinc-600">
              <p v-if="article.source">来源: {{ article.source }}</p>
              <p v-if="article.file_path" class="mt-1">文件: {{ article.file_path }}</p>
            </div>
            <div class="flex gap-3">
              <button 
                @click="copyContent"
                class="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10 transition-all"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                </svg>
                {{ copied ? '已复制' : '复制' }}
              </button>
            </div>
          </div>
        </div>
      </footer>
    </article>

    <!-- 文章不存在 -->
    <div v-else class="glass rounded-2xl p-16 text-center">
      <div class="w-20 h-20 mx-auto mb-6 rounded-full bg-red-500/10 flex items-center justify-center">
        <svg class="w-10 h-10 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
        </svg>
      </div>
      <h3 class="text-xl font-medium text-white mb-2">文章不存在</h3>
      <p class="text-zinc-500 mb-6">该文章可能已被删除或链接无效</p>
      <router-link to="/" class="btn-glow inline-flex items-center gap-2 px-6 py-3 rounded-xl text-white font-medium">
        返回书库
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { articleApi } from '../api'
import { useToast } from '../composables/useToast'

const { success, error } = useToast()
const route = useRoute()
const article = ref(null)
const loading = ref(true)
const copied = ref(false)

const copyContent = async () => {
  if (!article.value) return
  try {
    await navigator.clipboard.writeText(article.value.content)
    copied.value = true
    success('已复制到剪贴板')
    setTimeout(() => copied.value = false, 2000)
  } catch (e) {
    error('复制失败')
    console.error(e)
  }
}

onMounted(async () => {
  try {
    const { data } = await articleApi.getById(route.params.id)
    article.value = data
  } catch (e) {
    error('加载文章失败')
    console.error(e)
  }
  loading.value = false
})
</script>
