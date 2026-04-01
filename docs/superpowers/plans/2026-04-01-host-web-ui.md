# Host Web UI 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 OpenAgentic Host 服务构建 Web 交互界面，支持聊天和调试。

**Architecture:** React SPA，分屏布局（左聊天 / 右详情面板），通过 SSE 实时接收事件，REST API 交互。

**Tech Stack:** React 18, TypeScript, Tailwind CSS, react-markdown

**Spec:** `docs/superpowers/specs/2026-04-01-host-web-ui-design.md`

---

## Task 1: 项目初始化

**Files:**
- Create: `deploy/docker/web/package.json`
- Create: `deploy/docker/web/index.html`
- Create: `deploy/docker/web/tsconfig.json`
- Create: `deploy/docker/web/tailwind.config.js`
- Create: `deploy/docker/web/postcss.config.js`
- Create: `deploy/docker/web/vite.config.ts`

**Steps:**
- [ ] 创建 `package.json`，配置依赖：
  - react, react-dom
  - typescript, @types/react, @types/react-dom
  - tailwindcss, postcss, autoprefixer
  - vite, @vitejs/plugin-react
  - react-markdown, remark-gfm, prism-react-renderer
- [ ] 创建 `index.html` 入口文件
- [ ] 配置 TypeScript (`tsconfig.json`)
- [ ] 配置 Tailwind CSS (深色主题 + 自定义配色)
- [ ] 配置 Vite 构建

**Test:**
```bash
cd deploy/docker/web
npm install
npm run dev  # 应该能启动开发服务器
```

**Commit:** `feat(web): init React project with Vite + Tailwind`

---

## Task 2: 类型定义和 API Client

**Files:**
- Create: `deploy/docker/web/src/types/index.ts`
- Create: `deploy/docker/web/src/api/client.ts`

**Steps:**
- [ ] 定义 TypeScript 类型：
  ```typescript
  // types/index.ts
  interface Session { id: string; created_at: number; metadata: {...}; }
  interface Message { role: 'user' | 'assistant'; content: string; }
  interface Event { type: string; ts: number; seq: number; ... }
  interface TokenUsage { input: number; output: number; cost?: number; }
  interface WorkerStatus { ok: boolean; node_name: string; provider_ready: boolean; }
  ```
- [ ] 实现 API Client：
  - `createSession(title?: string): Promise<Session>`
  - `getSession(sessionId: string): Promise<Session>`
  - `sendMessage(sessionId: string, prompt: string): Promise<void>`
  - `getEvents(sessionId: string): Promise<Event[]>`
  - `getHealth(): Promise<WorkerStatus>`
  - `connectEventStream(onMessage: (e: Event) => void): EventSource`

**Test:**
```bash
# 手动验证 API client 能正确调用 Host
curl http://localhost:8766/health
```

**Commit:** `feat(web): add types and API client`

---

## Task 3: 全局状态和 Hooks

**Files:**
- Create: `deploy/docker/web/src/hooks/useSession.ts`
- Create: `deploy/docker/web/src/hooks/useEventStream.ts`
- Create: `deploy/docker/web/src/hooks/useWorkerStatus.ts`
- Create: `deploy/docker/web/src/App.tsx` (骨架)

**Steps:**
- [ ] `useSession` hook: 管理当前会话状态
  - `currentSessionId`, `sessions` list
  - `createSession()`, `switchSession()`, `loadHistory()`
- [ ] `useEventStream` hook: SSE 连接管理
  - 自动重连（指数退避）
  - 事件过滤（按 session_id）
  - `events` 数组，`connectionState` 状态
- [ ] `useWorkerStatus` hook: Worker 健康检查
  - 10 秒轮询 `/health`
  - `workerStatus` 状态

**Test:**
- 在 App 中临时使用 hooks，console.log 验证数据流

**Commit:** `feat(web): add global state hooks`

---

## Task 4: Header 组件

**Files:**
- Create: `deploy/docker/web/src/components/Header/index.tsx`
- Create: `deploy/docker/web/src/components/Header/SessionTitle.tsx`
- Create: `deploy/docker/web/src/components/Header/WorkerIndicator.tsx`

**Steps:**
- [ ] `WorkerIndicator`: 显示 Worker 状态点 + 名称
  - 绿色 = 在线，灰色 = 离线
- [ ] `SessionTitle`: 可编辑的会话标题
  - 点击进入编辑模式，Enter 或 blur 保存
- [ ] `Header`: 组合上述组件
  - Logo + SessionTitle + WorkerIndicator

**Test:**
- 可视化验证：状态点颜色变化，标题编辑功能

**Commit:** `feat(web): add Header components`

---

## Task 5: ChatPanel 组件

**Files:**
- Create: `deploy/docker/web/src/components/ChatPanel/index.tsx`
- Create: `deploy/docker/web/src/components/ChatPanel/MessageList.tsx`
- Create: `deploy/docker/web/src/components/ChatPanel/MessageItem.tsx`
- Create: `deploy/docker/web/src/components/ChatPanel/InputBox.tsx`

**Steps:**
- [ ] `MessageItem`: 单条消息渲染
  - 支持 Markdown (react-markdown + remark-gfm)
  - 代码高亮 (prism-react-renderer)
  - 用户消息右对齐蓝底，Assistant 左对齐灰底
- [ ] `MessageList`: 消息列表
  - 自动滚动到底部
  - 从 events 中提取 user.message 和 assistant.message
- [ ] `InputBox`: 多行输入框
  - Enter 发送，Shift+Enter 换行
  - 发送中禁用，显示 loading
- [ ] `ChatPanel`: 组合 MessageList + InputBox

**Test:**
- 发送消息，验证显示正确
- Markdown 和代码高亮验证

**Commit:** `feat(web): add ChatPanel components`

---

## Task 6: RightPanel 组件

**Files:**
- Create: `deploy/docker/web/src/components/RightPanel/index.tsx`
- Create: `deploy/docker/web/src/components/RightPanel/TabBar.tsx`
- Create: `deploy/docker/web/src/components/RightPanel/EventStream.tsx`
- Create: `deploy/docker/web/src/components/RightPanel/TokenStats.tsx`
- Create: `deploy/docker/web/src/components/RightPanel/SessionList.tsx`
- Create: `deploy/docker/web/src/components/RightPanel/WorkerStatus.tsx`

**Steps:**
- [ ] `TabBar`: 4 个标签切换（事件/Token/会话/Worker）
- [ ] `EventStream`: 实时事件流
  - 按时间倒序
  - 按类型着色
  - 可折叠详情
- [ ] `TokenStats`: Token 使用量 + 成本估算
  - 从 result 事件中累计 input_tokens + output_tokens
- [ ] `SessionList`: 历史会话列表
  - 显示标题 + 时间
  - 点击切换会话
- [ ] `WorkerStatus`: Worker 详细状态
  - 显示 /health 返回的全部信息
- [ ] `RightPanel`: 组合 TabBar + 内容区

**Test:**
- 各标签切换正常
- 事件流实时更新

**Commit:** `feat(web): add RightPanel components`

---

## Task 7: App 整合

**Files:**
- Update: `deploy/docker/web/src/App.tsx`
- Create: `deploy/docker/web/src/main.tsx`
- Create: `deploy/docker/web/src/index.css`

**Steps:**
- [ ] 整合布局：Header + ChatPanel (60%) + RightPanel (40%)
- [ ] 可拖拽分割线调整宽度（可选）
- [ ] 初始化逻辑：
  - 首次访问自动创建会话
  - 建立 SSE 连接
  - 启动 Worker 健康检查
- [ ] 全局样式：深色主题背景

**Test:**
```bash
npm run build
# 访问 http://localhost:8766 验证完整功能
```

**Commit:** `feat(web): integrate App layout`

---

## Task 8: Docker 集成

**Files:**
- Update: `deploy/docker/docker-compose-host.yml`
- Create: `deploy/docker/nginx.conf` (可选，如需 nginx)

**Steps:**
- [ ] 配置静态文件服务
  - 选项 A: Host 内嵌静态文件 (需修改 Python 代码)
  - 选项 B: 独立 nginx 容器
- [ ] 更新 docker-compose 添加 web 服务
- [ ] 配置 API 代理 (如需)

**Test:**
```bash
docker compose -f docker-compose-host.yml up -d
curl http://localhost:8766/  # 应返回 HTML
```

**Commit:** `feat(web): integrate with Docker`

---

## 执行顺序

```
Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 8
```

## 验证清单

- [ ] 能创建新会话
- [ ] 能发送消息并收到回复
- [ ] 事件流实时更新
- [ ] Token 统计正确
- [ ] 会话列表可切换
- [ ] Worker 状态显示正确
- [ ] 深色主题正常
- [ ] 移动端响应式（可选）
