import { test, expect } from '@playwright/test'

test('创作闭环：建项目 → 启动 → 逐环节确认 → 完成', async ({ page }) => {
  const projectId = `e2e_${Date.now().toString(36)}`

  await page.goto('/')
  await expect(page.getByRole('heading', { name: '我的小说', level: 2 })).toBeVisible()

  // 新建 short_story 项目
  await page.getByRole('button', { name: '新建项目' }).click()
  await page.getByPlaceholder('请输入书名').fill('e2e测试')
  await page.locator('select').selectOption('short_story')
  await page.getByPlaceholder('留空自动生成').fill(projectId)
  await page.getByRole('button', { name: '创建' }).click()

  // 进入工作台
  const card = page.getByRole('button', { name: new RegExp('e2e测试') }).first()
  await expect(card).toBeVisible()
  await card.click()

  // 输入立意并启动
  await page.getByPlaceholder('例：真假千金身份错位后重新定义家人').fill('测试立意')
  await page.getByRole('button', { name: '开始生成设定' }).click()

  // 逐环节确认（short_story = 1卷6章 → 约 18 次确认）
  const accept = page.getByRole('button', { name: '接受' })
  const doneVisible = () => page.getByText('创作完成').isVisible().catch(() => false)
  await expect(accept).toBeVisible({ timeout: 30000 })
  for (let i = 0; i < 40; i++) {
    if (await doneVisible()) break
    if ((await accept.count()) === 0) break
    await accept.click()
    await page.waitForTimeout(80) // 等待渲染收敛，避免点击已消失按钮的竞态
  }

  // 完成态 + 导出文件
  await expect(page.getByText('创作完成')).toBeVisible({ timeout: 30000 })
  await expect(page.getByText('.md')).toBeVisible()
  await expect(page.getByText('.txt')).toBeVisible()
})

test('写作基础库页可从后端加载性格条目', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '写作基础库' }).click()
  await expect(page.getByRole('heading', { name: '写作基础库', level: 2 })).toBeVisible()
  await expect(page.getByText('孤僻寡言型')).toBeVisible({ timeout: 15000 })
})

test('暗色模式切换', async ({ page }) => {
  await page.goto('/')
  const html = page.locator('html')
  await expect(html).not.toHaveClass(/dark/)
  await page.getByTitle('切换到暗色').click()
  await expect(html).toHaveClass(/dark/)
  await page.getByTitle('切换到亮色').click()
  await expect(html).not.toHaveClass(/dark/)
})
