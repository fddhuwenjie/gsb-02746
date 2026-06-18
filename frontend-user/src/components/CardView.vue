<template>
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
    <div v-for="article in articles" :key="article.id" @click="$emit('select', article.id)"
      class="glass rounded-2xl p-6 cursor-pointer card-hover group">
      <div class="w-14 h-14 bg-gradient-to-br from-primary-500 to-accent-500 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
        <span class="font-serif text-white text-xl font-semibold">{{ article.title[0] }}</span>
      </div>
      <h3 class="font-serif text-lg font-semibold text-gray-900 mb-2 line-clamp-2">{{ article.title }}</h3>
      <p v-if="article.content" class="text-gray-500 text-sm line-clamp-3 mb-4">
        {{ article.content.substring(0, 100) }}...
      </p>
      <div class="flex items-center justify-between text-sm">
        <span class="text-gray-400">
          <span v-if="article.author">{{ article.author }}</span>
        </span>
        <span v-if="article.year" class="text-gray-400">{{ article.year }}/{{ article.month }}</span>
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
.line-clamp-3 { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
</style>
