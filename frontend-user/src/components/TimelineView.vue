<template>
  <div class="relative">
    <div class="absolute left-6 top-0 bottom-0 w-0.5 bg-gradient-to-b from-primary-500 to-accent-500"></div>
    <div v-for="(article, index) in articles" :key="article.id" @click="$emit('select', article.id)"
      class="relative pl-16 pb-8 cursor-pointer group">
      <div class="absolute left-4 w-5 h-5 bg-white border-2 border-primary-500 rounded-full group-hover:bg-primary-500 transition-colors"></div>
      <div class="glass rounded-xl p-5 card-hover">
        <div class="flex items-start justify-between mb-2">
          <h3 class="font-serif text-lg font-semibold text-gray-900 group-hover:text-primary-600 transition-colors">
            {{ article.title }}
          </h3>
          <span v-if="article.category" class="px-2 py-1 bg-primary-100 text-primary-700 text-xs rounded-full ml-3 flex-shrink-0">
            {{ article.category }}
          </span>
        </div>
        <p v-if="article.content" class="text-gray-500 text-sm line-clamp-2 mb-3">
          {{ article.content.substring(0, 120) }}...
        </p>
        <div class="flex items-center gap-4 text-sm text-gray-400">
          <span v-if="article.author">{{ article.author }}</span>
          <span v-if="article.year">{{ article.year }}年{{ article.month }}月</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({ articles: Array })
defineEmits(['select'])
</script>

<style scoped>
.line-clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
</style>
