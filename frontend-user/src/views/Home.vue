<template>
  <div>
    <!-- 页面标题 -->
    <div class="mb-10">
      <h2 class="text-4xl font-serif font-bold gradient-text mb-3">探索阅读</h2>
      <p class="text-zinc-500">发现精选文章，开启心灵之旅</p>
    </div>

    <!-- 搜索和筛选栏 -->
    <div class="glass rounded-2xl p-6 mb-8">
      <div class="flex flex-col lg:flex-row gap-4">
        <!-- 搜索框 -->
        <div class="flex-1 relative">
          <div class="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
          </div>
          <input 
            v-model="search" 
            @input="debouncedSearch" 
            type="text" 
            placeholder="搜索文章标题、作者..."
            class="w-full pl-12 pr-4 py-4 rounded-xl bg-white/5 border border-white/10 text-white placeholder-zinc-500 focus:outline-none input-glow transition-all"
          >
        </div>

        <!-- 筛选器 -->
        <div class="flex gap-3">
          <select 
            v-model="filters.year" 
            @change="loadArticles"
            class="pl-4 pr-10 py-4 rounded-xl bg-white/5 border border-white/10 text-white focus:outline-none input-glow transition-all min-w-[120px] cursor-pointer appearance-none bg-[url('data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20fill%3D%22none%22%20viewBox%3D%220%200%2024%2024%22%20stroke%3D%22%239ca3af%22%3E%3Cpath%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%20stroke-width%3D%222%22%20d%3D%22M19%209l-7%207-7-7%22%2F%3E%3C%2Fsvg%3E')] bg-[length:20px] bg-[right_12px_center] bg-no-repeat"
          >
            <option value="" class="bg-zinc-900">全部年份</option>
            <option v-for="y in years" :key="y" :value="y" class="bg-zinc-900">{{ y }}年</option>
          </select>

          <select 
            v-model="filters.month" 
            @change="loadArticles"
            class="pl-4 pr-10 py-4 rounded-xl bg-white/5 border border-white/10 text-white focus:outline-none input-glow transition-all min-w-[120px] cursor-pointer appearance-none bg-[url('data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20fill%3D%22none%22%20viewBox%3D%220%200%2024%2024%22%20stroke%3D%22%239ca3af%22%3E%3Cpath%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%20stroke-width%3D%222%22%20d%3D%22M19%209l-7%207-7-7%22%2F%3E%3C%2Fsvg%3E')] bg-[length:20px] bg-[right_12px_center] bg-no-repeat"
          >
            <option value="" class="bg-zinc-900">全部月份</option>
            <option v-for="m in 12" :key="m" :value="m" class="bg-zinc-900">{{ m }}月</option>
          </select>

          <!-- 视图切换 -->
          <div class="flex rounded-xl bg-white/5 border border-white/10 p-1">
            <button 
              v-for="v in viewModes" 
              :key="v.value" 
              @click="viewMode = v.value"
              class="p-3 rounded-lg transition-all"
              :class="viewMode === v.value ? 'bg-gradient-to-r from-indigo-500 to-purple-500 text-white' : 'text-zinc-500 hover:text-white'"
              :title="v.label"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="v.icon"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- 统计信息 -->
      <div class="flex items-center gap-6 mt-4 pt-4 border-t border-white/5">
        <span class="text-zinc-500 text-sm">
          共 <span class="text-indigo-400 font-medium">{{ total }}</span> 篇文章
        </span>
        <span v-if="filters.year || filters.month || search" class="text-zinc-500 text-sm">
          当前筛选: 
          <span v-if="filters.year" class="tag px-2 py-0.5 rounded-md text-xs text-indigo-300 ml-1">{{ filters.year }}年</span>
          <span v-if="filters.month" class="tag px-2 py-0.5 rounded-md text-xs text-indigo-300 ml-1">{{ filters.month }}月</span>
          <span v-if="search" class="tag px-2 py-0.5 rounded-md text-xs text-indigo-300 ml-1">"{{ search }}"</span>
          <button @click="clearFilters" class="ml-2 text-zinc-400 hover:text-white transition-colors">清除</button>
        </span>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex flex-col items-center justify-center py-32">
      <div class="loader mb-4"></div>
      <p class="text-zinc-500">加载中...</p>
    </div>

    <!-- 空状态 -->
    <div v-else-if="articles.length === 0" class="glass rounded-2xl p-16 text-center">
      <div class="w-24 h-24 mx-auto mb-6 rounded-full bg-gradient-to-br from-indigo-500/20 to-purple-500/20 flex items-center justify-center">
        <svg class="w-12 h-12 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
        </svg>
      </div>
      <h3 class="text-xl font-medium text-white mb-2">书库暂无文章</h3>
      <p class="text-zinc-500 mb-6">开始抓取您喜爱的期刊文章吧</p>
      <router-link to="/crawler" class="btn-glow inline-flex items-center gap-2 px-6 py-3 rounded-xl text-white font-medium">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
        </svg>
        开始抓取
      </router-link>
    </div>

    <!-- 文章列表 -->
    <div v-else>
      <!-- 卡片视图 -->
      <div v-if="viewMode === 'card'" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <article 
          v-for="article in articles" 
          :key="article.id" 
          @click="openArticle(article.id)"
          class="glass rounded-2xl p-6 cursor-pointer card-hover group"
        >
          <div class="flex items-start justify-between mb-4">
            <div class="w-14 h-14 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 group-hover:shadow-indigo-500/40 transition-shadow">
              <span class="font-serif text-white text-xl font-bold">{{ article.title?.[0] || '文' }}</span>
            </div>
            <span v-if="article.category" class="tag px-3 py-1 rounded-full text-xs text-indigo-300">
              {{ article.category }}
            </span>
          </div>
          <h3 class="font-serif text-lg font-semibold text-white mb-2 line-clamp-2 group-hover:text-indigo-300 transition-colors">
            {{ article.title }}
          </h3>
          <p v-if="article.content" class="text-zinc-500 text-sm line-clamp-3 mb-4">
            {{ article.content.substring(0, 120) }}...
          </p>
          <div class="flex items-center justify-between text-sm pt-4 border-t border-white/5">
            <span class="text-zinc-500">{{ article.author || '佚名' }}</span>
            <span class="text-zinc-600">{{ article.year }}/{{ article.month }}</span>
          </div>
        </article>
      </div>

      <!-- 列表视图 -->
      <div v-else-if="viewMode === 'list'" class="space-y-4">
        <article 
          v-for="article in articles" 
          :key="article.id" 
          @click="openArticle(article.id)"
          class="glass rounded-xl p-5 cursor-pointer card-hover flex items-center gap-5 group"
        >
          <div class="w-14 h-14 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-indigo-500/20">
            <span class="font-serif text-white text-lg font-bold">{{ article.title?.[0] || '文' }}</span>
          </div>
          <div class="flex-1 min-w-0">
            <h3 class="font-medium text-white truncate group-hover:text-indigo-300 transition-colors">{{ article.title }}</h3>
            <p class="text-sm text-zinc-500 mt-1">
              {{ article.author || '佚名' }} · {{ article.year }}年{{ article.month }}月
              <span v-if="article.issue"> · {{ article.issue }}</span>
            </p>
          </div>
          <span v-if="article.category" class="tag px-3 py-1 rounded-full text-xs text-indigo-300 flex-shrink-0">
            {{ article.category }}
          </span>
          <svg class="w-5 h-5 text-zinc-600 group-hover:text-indigo-400 transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </article>
      </div>

      <!-- 时间线视图 -->
      <div v-else class="relative">
        <div class="absolute left-[7px] top-2 bottom-2 w-0.5 bg-gradient-to-b from-indigo-500 via-purple-500 to-pink-500"></div>
        <article 
          v-for="article in articles" 
          :key="article.id" 
          @click="openArticle(article.id)"
          class="relative pl-10 pb-8 cursor-pointer group"
        >
          <div class="absolute left-0 top-5 w-4 h-4 rounded-full bg-zinc-900 border-2 border-indigo-500 group-hover:bg-indigo-500 transition-colors"></div>
          <div class="glass rounded-xl p-5 card-hover">
            <div class="flex items-start justify-between mb-2">
              <h3 class="font-serif text-lg font-semibold text-white group-hover:text-indigo-300 transition-colors">
                {{ article.title }}
              </h3>
              <span v-if="article.category" class="tag px-2 py-1 rounded-md text-xs text-indigo-300 ml-3 flex-shrink-0">
                {{ article.category }}
              </span>
            </div>
            <p v-if="article.content" class="text-zinc-500 text-sm line-clamp-2 mb-3">
              {{ article.content.substring(0, 150) }}...
            </p>
            <div class="flex items-center gap-4 text-sm text-zinc-600">
              <span>{{ article.author || '佚名' }}</span>
              <span>{{ article.year }}年{{ article.month }}月</span>
            </div>
          </div>
        </article>
      </div>

      <!-- 分页 -->
      <div v-if="total > pageSize" class="flex justify-center items-center gap-2 mt-10">
        <button 
          @click="page > 1 && (page--, loadArticles())"
          :disabled="page === 1"
          class="p-2 rounded-lg bg-white/5 border border-white/10 text-zinc-400 hover:text-white hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
          </svg>
        </button>
        <div class="flex gap-1">
          <button 
            v-for="p in displayPages" 
            :key="p" 
            @click="p !== '...' && (page = p, loadArticles())"
            class="w-10 h-10 rounded-lg text-sm font-medium transition-all"
            :class="page === p 
              ? 'bg-gradient-to-r from-indigo-500 to-purple-500 text-white' 
              : p === '...' 
                ? 'text-zinc-600 cursor-default' 
                : 'bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10'"
          >
            {{ p }}
          </button>
        </div>
        <button 
          @click="page < totalPages && (page++, loadArticles())"
          :disabled="page === totalPages"
          class="p-2 rounded-lg bg-white/5 border border-white/10 text-zinc-400 hover:text-white hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { articleApi } from '../api'

const router = useRouter()
const articles = ref([])
const loading = ref(true)
const search = ref('')
const page = ref(1)
const pageSize = 12
const total = ref(0)
const filters = ref({ year: '', month: '' })
const viewMode = ref('card')
const years = ref([])

const viewModes = [
  { value: 'card', label: '卡片视图', icon: 'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z' },
  { value: 'list', label: '列表视图', icon: 'M4 6h16M4 12h16M4 18h16' },
  { value: 'timeline', label: '时间线视图', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' }
]

const totalPages = computed(() => Math.ceil(total.value / pageSize))
const displayPages = computed(() => {
  const pages = []
  const tp = totalPages.value
  if (tp <= 7) {
    for (let i = 1; i <= tp; i++) pages.push(i)
  } else {
    if (page.value <= 3) {
      pages.push(1, 2, 3, 4, '...', tp)
    } else if (page.value >= tp - 2) {
      pages.push(1, '...', tp - 3, tp - 2, tp - 1, tp)
    } else {
      pages.push(1, '...', page.value - 1, page.value, page.value + 1, '...', tp)
    }
  }
  return pages
})

let searchTimeout = null
const debouncedSearch = () => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => { page.value = 1; loadArticles() }, 300)
}

const clearFilters = () => {
  filters.value = { year: '', month: '' }
  search.value = ''
  page.value = 1
  loadArticles()
}

const loadArticles = async () => {
  loading.value = true
  try {
    const { data } = await articleApi.getList({
      page: page.value,
      page_size: pageSize,
      search: search.value || undefined,
      year: filters.value.year || undefined,
      month: filters.value.month || undefined
    })
    articles.value = data.items
    total.value = data.total
  } catch (e) {
    console.error(e)
  }
  loading.value = false
}

const loadIssues = async () => {
  try {
    const { data } = await articleApi.getIssues()
    years.value = [...new Set(data.map(i => i.year).filter(Boolean))].sort((a, b) => b - a)
  } catch (e) {
    console.error(e)
  }
}

const openArticle = (id) => router.push(`/article/${id}`)

onMounted(() => {
  loadArticles()
  loadIssues()
})
</script>

<style scoped>
.line-clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.line-clamp-3 { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
</style>
