/**
 * Settings 视图：
 *  - 挂载时从 settingsApi.get 取设置并填充到输入框
 *  - 修改 articles_path → 保存 → 调 settingsApi.update
 *  - 数据源表单：必填字段会触发浏览器原生 required（这里检查我们调用 API 的 payload）
 *  - 添加数据源后表单被重置
 *  - “一键添加模拟数据源”调用 addMockSource，并把后端返回的 message 通过 Toast 展示
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../src/api', () => ({
  settingsApi: {
    get: vi.fn(),
    update: vi.fn(),
    addSource: vi.fn(),
    addMockSource: vi.fn(),
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

import Settings from '../../src/views/Settings.vue'
import { settingsApi } from '../../src/api'

const mountSettings = () => mount(Settings)

describe('Settings.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    settingsApi.get.mockResolvedValue({ data: { articles_path: './data/articles' } })
  })

  it('从后端读取设置并显示在输入框中', async () => {
    const wrapper = mountSettings()
    await flushPromises()
    const input = wrapper.find('input[type="text"]') // 第一个 text input 是 articles_path
    expect(input.element.value).toBe('./data/articles')
  })

  it('保存设置：调用 update 并触发成功 Toast', async () => {
    settingsApi.update.mockResolvedValue({ data: { success: true } })
    const wrapper = mountSettings()
    await flushPromises()

    const input = wrapper.find('input[type="text"]')
    await input.setValue('./data/my_articles')
    const saveBtn = wrapper.findAll('button').find(b => b.text().includes('保存设置'))
    await saveBtn.trigger('click')
    await flushPromises()

    expect(settingsApi.update).toHaveBeenCalledWith({ articles_path: './data/my_articles' })
    expect(toastSpies.success).toHaveBeenCalledWith('设置已保存')
  })

  it('保存失败时把后端 detail 显示给用户', async () => {
    settingsApi.update.mockRejectedValue({
      response: { data: { detail: '路径不能包含 ;' } },
    })
    const wrapper = mountSettings()
    await flushPromises()
    const input = wrapper.find('input[type="text"]')
    await input.setValue('a;b')
    await wrapper.findAll('button').find(b => b.text().includes('保存设置')).trigger('click')
    await flushPromises()
    expect(toastSpies.error).toHaveBeenCalledWith('路径不能包含 ;')
  })

  it('添加数据源：表单提交后调用 addSource 并重置表单', async () => {
    settingsApi.addSource.mockResolvedValue({ data: { success: true } })
    const wrapper = mountSettings()
    await flushPromises()

    // 填写名称（form 内的输入按出现顺序：name, base_url, list_pattern, article_selector, title_selector, content_selector, author_selector, category_selector）
    const inputs = wrapper.findAll('form input')
    expect(inputs.length).toBeGreaterThanOrEqual(8)
    await inputs[0].setValue('我的源')
    await inputs[1].setValue('https://reader.example.com')
    await inputs[2].setValue('/{year}/{month}')
    await inputs[3].setValue('.item a')
    await inputs[4].setValue('h1.title')
    await inputs[5].setValue('.body')
    await inputs[6].setValue('.author')
    await inputs[7].setValue('.cat')

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(settingsApi.addSource).toHaveBeenCalledWith(expect.objectContaining({
      name: '我的源',
      base_url: 'https://reader.example.com',
      list_pattern: '/{year}/{month}',
      article_selector: '.item a',
      title_selector: 'h1.title',
      content_selector: '.body',
    }))
    expect(toastSpies.success).toHaveBeenCalledWith('数据源已添加')

    // 表单被重置：name 字段应回到空
    const inputsAfter = wrapper.findAll('form input')
    expect(inputsAfter[0].element.value).toBe('')
  })

  it('一键添加模拟数据源：把后端返回 message 通过 Toast 展示', async () => {
    settingsApi.addMockSource.mockResolvedValue({
      data: { message: '模拟数据源已添加', source: { name: '模拟数据源（测试用）' } },
    })
    const wrapper = mountSettings()
    await flushPromises()
    const btn = wrapper.findAll('button').find(b => b.text().includes('一键添加模拟数据源'))
    await btn.trigger('click')
    await flushPromises()
    expect(settingsApi.addMockSource).toHaveBeenCalled()
    expect(toastSpies.success).toHaveBeenCalledWith('模拟数据源已添加')
  })
})
