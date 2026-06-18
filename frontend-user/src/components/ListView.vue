<template>
  <div class="space-y-3">
    <div v-for="article in articles" :key="article.id" @click="$emit('select', article.id)"
      class="glass rounded-xl p-4 cursor-pointer card-hover flex items-center gap-4">
      <div class="w-12 h-12 bg-gradient-to-br from-primary-100 to-accent-100 rounded-lg flex items-center justify-center flex-shrink-0">
        <span class="font-serif text-primary-600 font-semibold">{{ article.title[0] }}</span>
      </div>
      <div class="flex-1 min-w-0">
        <h3 class="font-medium text-gray-900 truncate">{{ article.title }}</h3>
        <p class="text-sm text-gray-500">
          <span v-if="article.author">{{ article.author }} · </span>
          <span v-if="article.year">{{ article.year }}年{{ article.month }}月</span>
        </p>
      </div>
      <span v-if="article.category" class="px-3 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">
        {{ article.category }}
      </span>
    </div>
  </div>
</template>

<script setup>
defineProps({ articles: Array })
defineEmits(['select'])
</script>
