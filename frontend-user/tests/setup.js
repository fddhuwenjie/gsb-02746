// 全局测试 setup：清剪贴板与定时器，给每个测试一份干净环境
// 同时静默被组件 catch 后还会 console.error 的预期失败，避免 stderr 噪音让 CI 误判
import { vi, afterEach, beforeEach } from 'vitest'

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})
