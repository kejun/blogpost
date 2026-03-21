# Playwright 完整用法与生态工具指南

---

## 📦 安装与配置

### Node.js 安装
```bash
# 安装 Playwright
npm install -D playwright

# 安装浏览器（Chromium, Firefox, WebKit）
npx playwright install

# 或只安装特定浏览器
npx playwright install chromium
npx playwright install firefox
```

### Python 安装
```bash
pip install playwright
playwright install
```

### 系统依赖
```bash
# Ubuntu/Debian
npx playwright install-deps

# macOS
# 通常无需额外依赖

# Windows
# 自动安装所需依赖
```

---

## 🔧 核心 API 详解

### 1. 基础使用

#### Node.js
```javascript
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({
    headless: true,  // 无头模式
    slowMo: 100,     // 慢动作（调试用）
  });
  
  const page = await browser.newPage({
    viewport: { width: 1280, height: 720 },
    userAgent: 'Custom User Agent',
  });
  
  await page.goto('https://example.com');
  await page.screenshot({ path: 'example.png' });
  
  await browser.close();
})();
```

#### Python
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 720})
    
    page.goto('https://example.com')
    page.screenshot(path='example.png')
    
    browser.close()
```

### 2. 选择器与定位

```javascript
// CSS 选择器
await page.click('button.submit')
await page.fill('input#email', 'test@example.com')

// XPath
await page.click('//button[text()="Submit"]')
await page.locator('xpath=//div[@class="item"]').first()

// Text 选择器
await page.click('text=登录')
await page.click('"提交"')  // 简写

// Role 选择器（无障碍）
await page.click('role=button[name="Submit"]')
await page.click('role=link')

// 组合选择器
await page.locator('.item').filter({ hasText: '特定文本' }).click()
await page.locator('div').and(page.locator('.active'))

// 链式调用
await page
  .locator('ul')
  .locator('li')
  .filter({ hasText: '目标' })
  .click()
```

### 3. 等待机制

```javascript
// 自动等待（默认）
await page.click('button')  // 自动等待元素可见、可交互

// 显式等待
await page.waitForSelector('.loaded')  // 等待元素出现
await page.waitForSelector('.hidden', { state: 'hidden' })  // 等待隐藏
await page.waitForSelector('.deleted', { state: 'detached' })  // 等待删除

// 等待函数
await page.waitForFunction(() => {
  return document.querySelectorAll('.item').length > 10
})

// 等待网络请求
await page.waitForResponse('**/api/data')
await page.waitForRequest('**/api/login')

// 等待导航
await page.waitForNavigation()
await page.click('a', { waitUntil: 'networkidle' })

// 超时设置
await page.click('button', { timeout: 5000 })
await page.waitForSelector('.item', { timeout: 10000 })
```

### 4. 交互操作

```javascript
// 点击
await page.click('button')
await page.click('button', { clickCount: 2 })  // 双击
await page.click('button', { button: 'right' })  // 右键
await page.click('button', { modifiers: ['Control'] })  // Ctrl+ 点击

// 输入
await page.fill('input', '文本内容')
await page.type('input', '逐步输入', { delay: 100 })  // 模拟真实输入
await page.press('input', 'Enter')

// 选择下拉
await page.selectOption('select', 'value1')
await page.selectOption('select', { label: '选项文本' })
await page.selectOption('select', ['value1', 'value2'])  // 多选

// 拖拽
await page.dragAndDrop('#source', '#target')

// 悬停
await page.hover('button')

// 文件上传
await page.setInputFiles('input[type=file]', 'path/to/file.pdf')
await page.setInputFiles('input[type=file]', {
  name: 'file.txt',
  mimeType: 'text/plain',
  buffer: Buffer.from('文件内容')
})

// 对话框处理
page.on('dialog', async dialog => {
  console.log(dialog.message())
  await dialog.accept()  // 或 dialog.dismiss()
})
```

### 5. 截图与录屏

```javascript
// 截图
await page.screenshot({ path: 'full.png' })
await page.screenshot({ path: 'element.png', selector: '.item' })
await page.screenshot({ 
  path: 'fullpage.png',
  fullPage: true  // 完整页面
})

// 录屏
const browser = await chromium.launch()
const context = await browser.newContext()
await context.tracing.start({ screenshots: true, snapshots: true })

const page = await context.newPage()
await page.goto('https://example.com')

await context.tracing.stop({ path: 'trace.zip' })
// 使用 playwright show-trace trace.zip 查看
```

### 6. 网络拦截

```javascript
// 拦截请求
await page.route('**/api/*', route => {
  route.abort()  // 阻止请求
})

// Mock 响应
await page.route('**/api/users', route => {
  route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([{ id: 1, name: 'Mock User' }])
  })
})

// 修改请求头
await page.route('**/*', route => {
  const headers = route.request().headers()
  headers['X-Custom-Header'] = 'value'
  route.continue({ headers })
})

// 监听请求
page.on('request', request => {
  console.log('>>', request.method(), request.url())
})

page.on('response', response => {
  console.log('<<', response.status(), response.url())
})

// 等待特定请求
const [response] = await Promise.all([
  page.waitForResponse('**/api/submit'),
  page.click('button.submit')
])
console.log(await response.json())
```

### 7. 多标签页与上下文

```javascript
// 多标签页
const page1 = await browser.newPage()
const page2 = await browser.newPage()

// 监听新标签页
const [newPage] = await Promise.all([
  context.waitForEvent('page'),
  page.click('a[target="_blank"]')
])
await newPage.waitForLoadState()

// 浏览器上下文（隔离环境）
const context = await browser.newContext({
  viewport: { width: 1280, height: 720 },
  userAgent: 'Custom Agent',
  locale: 'zh-CN',
  timezoneId: 'Asia/Shanghai',
  permissions: ['geolocation'],
  geolocation: { longitude: 121.4737, latitude: 31.2304 },
})

// 持久化存储（类似用户配置文件）
const context = await browser.newContext({
  storageState: 'auth.json',  // 保存的登录状态
})

// 保存状态
await context.storageState({ path: 'auth.json' })
```

### 8. 认证与登录

```javascript
// 方法 1：保存登录状态
// 首次登录
const context = await browser.newContext()
const page = await context.newPage()
await page.goto('https://example.com/login')
await page.fill('input[name=username]', 'user')
await page.fill('input[name=password]', 'pass')
await page.click('button[type=submit')
await context.storageState({ path: 'auth.json' })

// 后续使用保存的状态
const authContext = await browser.newContext({
  storageState: 'auth.json'
})

// 方法 2：全局认证
await context.addCookies([{
  name: 'session',
  value: 'xxx',
  domain: 'example.com',
  path: '/'
}])

// 方法 3：HTTP 认证
const context = await browser.newContext({
  httpCredentials: {
    username: 'user',
    password: 'pass'
  }
})
```

### 9. iframe 处理

```javascript
// 获取 iframe
const frame = page.frame({ name: 'iframe-name' })
await frame.fill('input', 'text')

// 通过选择器
const frame = page.frameLocator('iframe.src').first()
await frame.locator('button').click()

// 嵌套 iframe
const nested = page
  .frameLocator('iframe.parent')
  .frameLocator('iframe.child')
await nested.locator('button').click()
```

### 10. 测试用例（Playwright Test）

```javascript
// test.spec.js
const { test, expect } = require('@playwright/test');

test.describe('登录功能', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('https://example.com')
  })

  test('成功登录', async ({ page }) => {
    await page.fill('input[name=username]', 'correct-user')
    await page.fill('input[name=password]', 'correct-pass')
    await page.click('button[type=submit]')
    
    await expect(page).toHaveURL('https://example.com/dashboard')
    await expect(page.locator('.welcome')).toContainText('欢迎')
  })

  test('失败登录', async ({ page }) => {
    await page.fill('input[name=username]', 'wrong-user')
    await page.fill('input[name=password]', 'wrong-pass')
    await page.click('button[type=submit]')
    
    await expect(page.locator('.error')).toBeVisible()
  })

  test('参数化测试', async ({ page }, testInfo) => {
    const users = [
      { user: 'user1', pass: 'pass1' },
      { user: 'user2', pass: 'pass2' }
    ]
    
    for (const { user, pass } of users) {
      await page.fill('input[name=username]', user)
      await page.fill('input[name=password]', pass)
      await page.click('button[type=submit]')
      await expect(page.locator('.success')).toBeVisible()
    }
  })
})
```

---

## 🛠️ 生态工具

### 1. Playwright Test（测试框架）

```bash
npm install -D @playwright/test
npx playwright install
```

```javascript
// playwright.config.js
module.exports = {
  testDir: './tests',
  timeout: 30000,
  retries: 2,
  workers: 4,
  use: {
    headless: true,
    viewport: { width: 1280, height: 720 },
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
    { name: 'firefox', use: { browserName: 'firefox' } },
    { name: 'webkit', use: { browserName: 'webkit' } },
    { name: 'Mobile Chrome', use: { ...devices['Pixel 5'] } },
    { name: 'Mobile Safari', use: { ...devices['iPhone 12'] } },
  ],
  reporter: [['html'], ['json', { outputFile: 'results.json' }]],
}
```

```bash
# 运行测试
npx playwright test

# 运行特定测试
npx playwright test login.spec.js
npx playwright test --grep "登录"

# 调试模式
npx playwright test --debug

# 生成测试
npx playwright codegen https://example.com

# 显示报告
npx playwright show-report
```

### 2. Codegen（代码生成器）

```bash
# 录制操作生成代码
npx playwright codegen https://example.com

# 指定语言
npx playwright codegen --target python https://example.com
npx playwright codegen --target python-async https://example.com
npx playwright codegen --target java https://example.com
```

### 3. Trace Viewer（追踪查看器）

```bash
# 查看追踪文件
npx playwright show-trace trace.zip

# 在 CI 中保存追踪
# playwright.config.js
use: {
  trace: 'on-first-retry'
}
```

### 4. UI Mode（UI 模式）

```bash
# 交互式 UI 模式
npx playwright test --ui

# 功能：
# - 实时查看测试
# - 时间旅行调试
# - 选择器探索
# - 快速修复
```

### 5. Docker 支持

```bash
# 使用官方镜像
docker run -v $(pwd):/work/ mcr.microsoft.com/playwright:v1.40.0 /bin/bash

# GitHub Actions
jobs:
  test:
    runs-on: ubuntu-latest
    container:
      image: mcr.microsoft.com/playwright:v1.40.0
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npx playwright test
```

### 6. 第三方集成

#### Visual Regression（视觉回归）
```bash
npm install -D @playwright/test
```

```javascript
// 截图对比
test('视觉回归', async ({ page }) => {
  await page.goto('https://example.com')
  await expect(page).toHaveScreenshot()
})

// 更新基准截图
npx playwright test --update-snapshots
```

#### API 测试
```javascript
const { test, expect } = require('@playwright/test');

test('API 测试', async ({ request }) => {
  const response = await request.post('/api/login', {
    data: { username: 'user', password: 'pass' }
  })
  
  expect(response.ok()).toBeTruthy()
  const data = await response.json()
  expect(data.token).toBeDefined()
})
```

#### 性能测试
```javascript
test('性能测试', async ({ page }) => {
  const client = await page.context().newCDPSession(page)
  await client.send('Performance.enable')
  
  await page.goto('https://example.com')
  
  const metrics = await client.send('Performance.getMetrics')
  console.log(metrics.metrics)
})
```

---

## 📚 实战示例

### 1. 登录自动化
```javascript
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch()
  const page = await browser.newPage()
  
  await page.goto('https://example.com/login')
  await page.fill('input[name=username]', 'user@example.com')
  await page.fill('input[name=password]', 'password123')
  await page.click('button[type=submit]')
  
  await page.waitForURL('**/dashboard')
  await page.screenshot({ path: 'dashboard.png' })
  
  await browser.close()
})()
```

### 2. 数据抓取
```javascript
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch()
  const page = await browser.newPage()
  
  await page.goto('https://example.com/products')
  
  // 等待内容加载
  await page.waitForSelector('.product-item')
  
  // 提取数据
  const products = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('.product-item')).map(el => ({
      name: el.querySelector('.name')?.textContent,
      price: el.querySelector('.price')?.textContent,
      rating: el.querySelector('.rating')?.textContent,
    }))
  })
  
  console.log(products)
  await browser.close()
})()
```

### 3. 多页面测试
```javascript
const { test, expect } = require('@playwright/test');

test('多标签页测试', async ({ browser }) => {
  const context = await browser.newContext()
  const page = await context.newPage()
  
  await page.goto('https://example.com')
  
  // 打开新标签页
  const [newPage] = await Promise.all([
    context.waitForEvent('page'),
    page.click('a[target="_blank"]')
  ])
  
  await newPage.waitForLoadState()
  expect(newPage.url()).toContain('external-site')
  
  await browser.close()
})
```

### 4. 文件下载
```javascript
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch()
  const page = await browser.newPage()
  
  // 设置下载路径
  page.on('download', async download => {
    const path = await download.path()
    console.log('文件下载到:', path)
    await download.saveAs('./downloads/' + download.suggestedFilename())
  })
  
  await page.goto('https://example.com/files')
  await page.click('a.download')
  
  await browser.close()
})()
```

### 5. 移动端测试
```javascript
const { devices } = require('playwright');

(async () => {
  const browser = await chromium.launch()
  
  // iPhone 12
  const iphone = await browser.newContext({
    ...devices['iPhone 12 Pro'],
  })
  const page = await iphone.newPage()
  await page.goto('https://example.com')
  await page.screenshot({ path: 'iphone.png' })
  
  // Pixel 5
  const pixel = await browser.newContext({
    ...devices['Pixel 5'],
  })
  const page2 = await pixel.newPage()
  await page2.goto('https://example.com')
  await page2.screenshot({ path: 'android.png' })
  
  await browser.close()
})()
```

---

## ⚠️ 最佳实践

### 1. 稳定的选择器
```javascript
// ✅ 推荐：使用语义化选择器
await page.click('role=button[name="提交"]')
await page.fill('input[aria-label="邮箱"]', 'test@example.com')
await page.click('data-testid=submit-button')

// ❌ 避免：脆弱的选择器
await page.click('div > span:nth-child(3)')
await page.click('.btn.btn-primary.mr-2')
```

### 2. 正确的等待
```javascript
// ✅ 推荐：使用内置等待
await page.click('button')  // 自动等待
await expect(page.locator('.item')).toBeVisible()

// ❌ 避免：硬编码等待
await page.waitForTimeout(5000)  // 不要这样做
```

### 3. Page Object 模式
```javascript
class LoginPage {
  constructor(page) {
    this.page = page
    this.usernameInput = page.locator('input[name=username]')
    this.passwordInput = page.locator('input[name=password]')
    this.submitButton = page.locator('button[type=submit]')
  }
  
  async goto() {
    await this.page.goto('/login')
  }
  
  async login(username, password) {
    await this.usernameInput.fill(username)
    await this.passwordInput.fill(password)
    await this.submitButton.click()
  }
}

// 使用
const loginPage = new LoginPage(page)
await loginPage.goto()
await loginPage.login('user', 'pass')
```

### 4. 错误处理
```javascript
try {
  await page.click('button', { timeout: 5000 })
} catch (error) {
  await page.screenshot({ path: 'error.png' })
  throw error
}

// 重试逻辑
for (let i = 0; i < 3; i++) {
  try {
    await page.click('button')
    break
  } catch (e) {
    if (i === 2) throw e
    await page.waitForTimeout(1000)
  }
}
```

---

## 🔗 相关资源

### 官方文档
- [Playwright Docs](https://playwright.dev/)
- [API Reference](https://playwright.dev/docs/api/class-playwright)
- [GitHub](https://github.com/microsoft/playwright)

### 工具
- [Playwright Test](https://playwright.dev/docs/test-intro)
- [Codegen](https://playwright.dev/docs/codegen)
- [Trace Viewer](https://playwright.dev/docs/trace-viewer)
- [UI Mode](https://playwright.dev/docs/test-ui-mode)

### 社区
- [Discord](https://aka.ms/playwright/discord)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/playwright)

---

*最后更新：2026-03-21*
