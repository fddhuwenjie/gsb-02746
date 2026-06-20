/**
 * Article 详情页：
 *  - 加载成功时展示标题/作者/正文/期数
 *  - 复制按钮调用 navigator.clipboard 并触发 Toast
 *  - 复制失败（clipboard 抛错）走 error 分支但不崩
 *  - 后端返回 404 时仍然渲染兜底 UI（"文章不存在"）
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../src/api', () => ({
  articleApi: {
    getById: vi.fn(),
  },
}))

const toastSpies = { success: vi.fn(), error: vi.fn() }
vi.mock('../../src/composables/useToast', () => ({
  useToast: () => ({
    success: toastSpies.success,
    error: toastSpies.error,
    show: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    hide: vi.fn(),
    toastState: { value: { visible: false, message: '', type: 'info', duration: 0 } },
  }),
}))

vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return { ...actual, useRoute: () => ({ params: { id: '7' } }) }
})

import Article from '../../src/views/Article.vue'
import { articleApi } from '../../src/api'

const mountArticle = () =>
  mount(Article, {
    global: {
      stubs: { 'router-link': { template: '<a><slot /></a>' } },
    },
  })

describe('Article.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('成功加载时正确渲染元信息和正文', async () => {
    articleApi.getById.mockResolvedValue({
      data: {
        id: 7, title: '人生的意义', author: '张三', content: '人生很美好',
        year: 2024, month: 1, issue: '第1期', category: '感悟', source: '读者',
      },
    })
    const wrapper = mountArticle()
    await flushPromises()
    expect(wrapper.text()).toContain('人生的意义')
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('人生很美好')
    expect(wrapper.text()).toContain('第1期')
    expect(wrapper.text()).toContain('2024年1月')
  })

  it('复制按钮把正文写入剪贴板并触发成功 Toast', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    articleApi.getById.mockResolvedValue({
      data: { id: 7, title: 't', content: 'COPY-ME', year: 2024, month: 1 },
    })
    const wrapper = mountArticle()
    await flushPromises()

    const copyBtn = wrapper.findAll('button').find(b => b.text().includes('复制'))
    expect(copyBtn).toBeTruthy()
    await copyBtn.trigger('click')
    await flushPromises()

    expect(writeText).toHaveBeenCalledWith('COPY-ME')
    expect(toastSpies.success).toHaveBeenCalledWith('已复制到剪贴板')
    // 按钮文案应切换到「已复制」
    expect(copyBtn.text()).toContain('已复制')
  })

  it('剪贴板失败时走 error 分支且不抛', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    Object.assign(navigator, { clipboard: { writeText } })

    articleApi.getById.mockResolvedValue({
      data: { id: 7, title: 't', content: 'x', year: 2024, month: 1 },
    })
    const wrapper = mountArticle()
    await flushPromises()
    const copyBtn = wrapper.findAll('button').find(b => b.text().includes('复制'))
    await copyBtn.trigger('click')
    await flushPromises()

    expect(toastSpies.error).toHaveBeenCalledWith('复制失败')
    expect(toastSpies.success).not.toHaveBeenCalled()
  })

  it('请求失败时渲染兜底"文章不存在"卡片', async () => {
    articleApi.getById.mockRejectedValue({ response: { status: 404 } })
    const wrapper = mountArticle()
    await flushPromises()
    expect(wrapper.text()).toContain('文章不存在')
    expect(toastSpies.error).toHaveBeenCalled()
  })
})
