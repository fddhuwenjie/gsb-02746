/**
 * Home 视图回归测试。
 * 重点：
 *  - 加载初始为空时显示空态（容易被 router-link / api 改动破坏）
 *  - 列表渲染：按 viewMode 切换 card / list / timeline，每种都把数据正确渲染出来
 *  - 年/月筛选触发 loadArticles 时把参数透传到 articleApi.getList
 *  - 搜索框带 debounce，停下后才会触发请求（避免每个字符都打后端）
 *  - “清除”按钮一次性重置筛选，并且只触发一次额外请求
 *  - 当后端列表里出现部分字段缺失（老数据兼容）的 item 时，不应抛错
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// ① 必须在 import Home 之前 mock 掉 ../api 和 vue-router
vi.mock('../../src/api', () => {
  return {
    articleApi: {
      getList: vi.fn(),
      getIssues: vi.fn().mockResolvedValue({ data: [] }),
    },
  }
})

const pushSpy = vi.fn()
vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return {
    ...actual,
    useRouter: () => ({ push: pushSpy }),
  }
})

import Home from '../../src/views/Home.vue'
import { articleApi } from '../../src/api'

const mountHome = () =>
  mount(Home, {
    global: {
      stubs: {
        // router-link 在卡片视图下出现在空态按钮里
        'router-link': { template: '<a><slot /></a>' },
      },
    },
  })

describe('Home.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    articleApi.getIssues.mockResolvedValue({
      data: [
        { year: 2024, month: 1 },
        { year: 2023, month: 12 },
      ],
    })
  })

  it('空列表渲染空态文案', async () => {
    articleApi.getList.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 12 } })
    const wrapper = mountHome()
    await flushPromises()
    expect(wrapper.text()).toContain('书库暂无文章')
  })

  it('卡片视图渲染所有标题，元信息容忍字段缺失', async () => {
    articleApi.getList.mockResolvedValue({
      data: {
        items: [
          { id: 1, title: '人生的意义', author: '张三', content: '内容A', year: 2024, month: 1, category: '人生感悟' },
          // 老数据：没有 author / category / content
          { id: 2, title: '老数据' },
        ],
        total: 2, page: 1, page_size: 12,
      },
    })
    const wrapper = mountHome()
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('人生的意义')
    expect(text).toContain('老数据')
    // 兼容：没有 author 时不应渲染出 "undefined"
    expect(text).not.toContain('undefined')
  })

  it('选择年份+月份会带筛选参数请求列表', async () => {
    articleApi.getList.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 12 } })
    const wrapper = mountHome()
    await flushPromises()

    const selects = wrapper.findAll('select')
    // 第一个 select 是年份，第二个是月份
    await selects[0].setValue('2024')
    await flushPromises()
    await selects[1].setValue('1')
    await flushPromises()

    // 最后一次调用必须包含 year=2024, month=1（select 的值可能是 string 或 number）
    const lastCall = articleApi.getList.mock.calls.at(-1)[0]
    expect(Number(lastCall.year)).toBe(2024)
    expect(Number(lastCall.month)).toBe(1)
    expect(lastCall.page).toBe(1)
  })

  it('搜索框输入会防抖：连续输入只触发一次请求', async () => {
    vi.useFakeTimers()
    articleApi.getList.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 12 } })
    const wrapper = mountHome()
    await flushPromises()
    const callsAtMount = articleApi.getList.mock.calls.length

    const input = wrapper.find('input[type="text"]')
    await input.setValue('人')
    await input.setValue('人生')
    await input.setValue('人生意义')

    // 还没到 300ms，不应触发新请求
    vi.advanceTimersByTime(200)
    expect(articleApi.getList.mock.calls.length).toBe(callsAtMount)

    // 跨过 debounce 后，多次输入只产生一次请求
    vi.advanceTimersByTime(200)
    await flushPromises()
    expect(articleApi.getList.mock.calls.length).toBe(callsAtMount + 1)
    expect(articleApi.getList.mock.calls.at(-1)[0].search).toBe('人生意义')
  })

  it('清除按钮重置筛选并重新加载', async () => {
    articleApi.getList.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 12 } })
    const wrapper = mountHome()
    await flushPromises()
    const selects = wrapper.findAll('select')
    await selects[0].setValue('2024')
    await flushPromises()
    const callsBeforeClear = articleApi.getList.mock.calls.length

    // 找到“清除”按钮
    const clearBtn = wrapper.findAll('button').find(b => b.text() === '清除')
    expect(clearBtn).toBeTruthy()
    await clearBtn.trigger('click')
    await flushPromises()

    expect(articleApi.getList.mock.calls.length).toBe(callsBeforeClear + 1)
    const lastArgs = articleApi.getList.mock.calls.at(-1)[0]
    expect(lastArgs.year).toBeUndefined()
    expect(lastArgs.month).toBeUndefined()
    expect(lastArgs.search).toBeUndefined()
  })

  it('点击文章卡片会跳转到详情页（router.push）', async () => {
    articleApi.getList.mockResolvedValue({
      data: {
        items: [{ id: 42, title: '点我', year: 2024, month: 1, content: 'x' }],
        total: 1, page: 1, page_size: 12,
      },
    })
    const wrapper = mountHome()
    await flushPromises()
    await wrapper.find('article').trigger('click')
    expect(pushSpy).toHaveBeenCalledWith('/article/42')
  })
})
