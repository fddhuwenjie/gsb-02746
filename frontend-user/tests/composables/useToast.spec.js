/**
 * useToast 单元测试。
 * 这个组合式函数有一个隐藏脆弱点：模块级 timer 是单例，
 * 多次调用会互相影响。测试主要覆盖：
 *  - success/error 等便捷方法把 type 写对
 *  - duration 之后自动隐藏
 *  - 第二次调用应该把上一个 timer 取消，不会因为旧 timer 把新消息也隐藏掉
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { useToast } from '../../src/composables/useToast'

afterEach(() => {
  // 清掉 module-level 状态
  const { hide } = useToast()
  hide()
})

describe('useToast', () => {
  it('success 设置正确的 type 和 message', () => {
    const { success, toastState } = useToast()
    success('已保存')
    expect(toastState.value.visible).toBe(true)
    expect(toastState.value.type).toBe('success')
    expect(toastState.value.message).toBe('已保存')
  })

  it('duration 后自动隐藏', () => {
    vi.useFakeTimers()
    const { error, toastState } = useToast()
    error('坏了', 1000)
    expect(toastState.value.visible).toBe(true)
    vi.advanceTimersByTime(999)
    expect(toastState.value.visible).toBe(true)
    vi.advanceTimersByTime(1)
    expect(toastState.value.visible).toBe(false)
    vi.useRealTimers()
  })

  it('快速连续调用：旧 timer 不会把新消息提前隐藏', () => {
    vi.useFakeTimers()
    const { info, toastState } = useToast()
    info('first', 1000)
    vi.advanceTimersByTime(900)
    info('second', 1000) // 应当重置 timer
    vi.advanceTimersByTime(200) // 累计 1100ms：旧的早超时，但新 timer 才走 200
    expect(toastState.value.visible).toBe(true)
    expect(toastState.value.message).toBe('second')
    vi.advanceTimersByTime(800)
    expect(toastState.value.visible).toBe(false)
    vi.useRealTimers()
  })
})
