import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Home', component: () => import('../views/Home.vue') },
  { path: '/article/:id', name: 'Article', component: () => import('../views/Article.vue') },
  { path: '/crawler', name: 'Crawler', component: () => import('../views/Crawler.vue') },
  { path: '/settings', name: 'Settings', component: () => import('../views/Settings.vue') }
]

export default createRouter({
  history: createWebHistory(),
  routes
})
