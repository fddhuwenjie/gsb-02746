/**
 * Crawler 视图：
 *  - 挂载时加载 sources 列表，无源时显示「提供网站地址」兜底
 *  - 「一键模拟抓取」调用 mock 接口，并把成功状态显示在状态条
 *  - 「添加测试数据」调用 articleApi.seed
 *  - 真实抓取的 polling 行为：start 后每秒查 status，直到 completed 停止 polling 并 Toast 完成
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../src/api', () => ({
  crawlerApi: {
    start: vi.fn(),
    getStatus: vi.fn(),
    getSources: vi.fn(),
    mock: vi.fn(),
  },
  articleApi: {
    seed: vi.fn(),
  },
}))

const toastSpies = { success: vi.fn(), error: vi.fn() }
vi.mock('../../src/composables/useToast', () => ({
  useToast: () => ({
    success: toastSpies.success, error: toastSpies.error,
    show: vi.fn(), warning: vi.fn(), info: vi.fn(), hide: vi.fn(),
    toastState: { value: { visible: false, message: '', type: 'info', duration: 0 } },
  }),
}))

import Crawler from '../../src/views/Crawler.vue'
import { crawlerApi, articleApi } from '../../src/api'

const mountCrawler = () =>
  mount(Crawler, {
    global: {
      stubs: { 'router-link': { template: '<a><slot /></a>' } },
    },
  })

describe('Crawler.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    crawlerApi.getSources.mockResolvedValue({ data: { sources: [] } })
  })

  it('无数据源时显示"提供网站地址"兜底文案', async () => {
    const wrapper = mountCrawler()
    await flushPromises()
    expect(wrapper.text()).toContain('提供网站地址')
    expect(wrapper.text()).toContain('暂无配置的数据源')
  })

  it('已有数据源时正常列出', async () => {
    crawlerApi.getSources.mockResolvedValue({
      data: { sources: [{ name: '读者在线', base_url: 'https://reader.example.com' }] },
    })
    const wrapper = mountCrawler()
    await flushPromises()
    expect(wrapper.text()).toContain('读者在线')
    expect(wrapper.text()).toContain('https://reader.example.com')
  })

  it('一键模拟抓取：成功后显示完成状态与文章数', async () => {
    crawlerApi.mock.mockResolvedValue({
      data: { success: true, articles_count: 3, message: '模拟抓取成功，已添加 3 篇文章' },
    })
    const wrapper = mountCrawler()
    await flushPromises()
    const btn = wrapper.findAll('button').find(b => b.text().includes('一键模拟抓取'))
    await btn.trigger('click')
    await flushPromises()
    expect(crawlerApi.mock).toHaveBeenCalled()
    expect(toastSpies.success).toHaveBeenCalledWith('模拟抓取成功，已添加 3 篇文章')
    // 状态条出现 “模拟抓取完成”
    expect(wrapper.text()).toContain('模拟抓取完成')
    expect(wrapper.text()).toContain('3')
  })

  it('添加测试数据：调用 articleApi.seed 并 Toast 后端 message', async () => {
    articleApi.seed.mockResolvedValue({ data: { message: '已添加 8 篇测试文章' } })
    const wrapper = mountCrawler()
    await flushPromises()
    const btn = wrapper.findAll('button').find(b => b.text().includes('添加测试数据'))
    await btn.trigger('click')
    await flushPromises()
    expect(articleApi.seed).toHaveBeenCalled()
    expect(toastSpies.success).toHaveBeenCalledWith('已添加 8 篇测试文章')
  })

  it('开始抓取：轮询 status 直到 completed，停止轮询并 Toast 完成', async () => {
    vi.useFakeTimers()
    crawlerApi.start.mockResolvedValue({ data: { message: '抓取任务已启动' } })

    // 第一次轮询返回 running，第二次返回 completed
    crawlerApi.getStatus
      .mockResolvedValueOnce({ data: { status: 'running', message: '抓取中', articles_count: 0 } })
      .mockResolvedValueOnce({ data: { status: 'completed', message: '抓取完成', articles_count: 5 } })

    const wrapper = mountCrawler()
    await flushPromises()
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(crawlerApi.start).toHaveBeenCalled()

    // tick 1: still running
    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()
    expect(toastSpies.success).not.toHaveBeenCalled()

    // tick 2: completed → 弹 success Toast
    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()
    expect(toastSpies.success).toHaveBeenCalledWith('抓取完成，共 5 篇文章')

    // 进一步 tick 不再调用 getStatus（轮询已停）
    const statusCallsBefore = crawlerApi.getStatus.mock.calls.length
    await vi.advanceTimersByTimeAsync(3000)
    expect(crawlerApi.getStatus.mock.calls.length).toBe(statusCallsBefore)
  })

  it('开始抓取失败（无数据源）时显示后端 detail', async () => {
    crawlerApi.start.mockRejectedValue({
      response: { data: { detail: '请先配置数据源' } },
    })
    const wrapper = mountCrawler()
    await flushPromises()
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(toastSpies.error).toHaveBeenCalledWith('请先配置数据源')
    expect(wrapper.text()).toContain('请先配置数据源')
  })
})
