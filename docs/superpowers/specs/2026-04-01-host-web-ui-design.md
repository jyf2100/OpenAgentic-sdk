# Host Web UI 设计文档

## 概述

为 OpenAgentic Host 服务设计 Web 交互界面，支持开发调试和日常聊天使用。

## 需求

- **使用场景**: 开发调试 + 日常聊天
- **交互形式**: Web 网页
- **技术栈**: React + TypeScript + Tailwind CSS

## 界面布局

### 整体架构 (方案 A: 单页分屏)

```
┌─────────────────────────────────────────────────────────┐
│  Header                                                  │
│  - Logo / Title                                          │
│  - 当前会话标题 (可编辑)                                  │
│  - Worker 状态: ● worker-0 (绿色=在线, 灰色=离线)        │
├──────────────────────────┬──────────────────────────────┤
│                          │  Tab Bar                      │
│                          │  [事件] [Token] [会话] [Worker]│
│      Chat Panel          ├──────────────────────────────┤
│  ┌────────────────────┐  │                              │
│  │  User: xxx         │  │   Tab Content                │
│  │  Assistant: xxx    │  │   (根据选中标签显示)          │
│  │  ...               │  │                              │
│  └────────────────────┘  │                              │
│  ┌────────────────────┐  │                              │
│  │  输入框 + 发送按钮  │  │                              │
│  └────────────────────┘  │                              │
│                          │                              │
└──────────────────────────┴──────────────────────────────┘
```

**宽度比例**: 左侧 60% / 右侧 40%（可拖拽调整）

## 核心组件

### Header
- `SessionTitle` - 可编辑的会话标题
- `WorkerIndicator` - 在线状态点 + Worker 名称

### ChatPanel (左侧)
- `MessageList` - 消息流，支持滚动加载历史
- `MessageItem` - 单条消息，支持 markdown 渲染
- `InputBox` - 多行输入框 + 发送按钮，Enter 发送

### RightPanel (右侧)
- `TabBar` - 4 个标签切换
- `EventStream` - 实时事件流，按时间倒序，可折叠
- `TokenStats` - 当前会话的 token 使用量 + 成本估算
- `SessionList` - 历史会话列表，点击切换
- `WorkerStatus` - Worker 连接状态、健康检查

## API 交互

### 主要端点

```typescript
// 创建会话
POST /session → { id, created_at, metadata }

// 发送消息 (异步)
POST /session/{id}/prompt_async → 204 No Content

// 获取历史事件
GET /session/{id}/events → { entries: [...] }

// 实时事件流 (SSE)
GET /event → text/event-stream

// 健康检查
GET /health → { ok, provider_ready, ... }
```

### 数据流策略

- **实时更新**: SSE `/event` 监听新事件
- **历史加载**: 进入会话时 GET `/session/{id}/events`
- **Worker 状态**: 轮询 `/health` (10秒一次)

### 状态管理

```typescript
interface AppState {
  currentSessionId: string | null;
  messages: Message[];
  events: Event[];
  tokenUsage: TokenUsage;
  sessions: Session[];
  workerStatus: WorkerStatus;
  connectionState: 'connected' | 'reconnecting' | 'offline';
}
```

## 技术实现

### 目录结构

```
deploy/docker/web/
├── index.html
├── package.json
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── components/
│   │   ├── Header/
│   │   │   ├── index.tsx
│   │   │   ├── SessionTitle.tsx
│   │   │   └── WorkerIndicator.tsx
│   │   ├── ChatPanel/
│   │   │   ├── index.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── MessageItem.tsx
│   │   │   └── InputBox.tsx
│   │   ├── RightPanel/
│   │   │   ├── index.tsx
│   │   │   ├── TabBar.tsx
│   │   │   ├── EventStream.tsx
│   │   │   ├── TokenStats.tsx
│   │   │   ├── SessionList.tsx
│   │   │   └── WorkerStatus.tsx
│   │   └── common/
│   │       ├── Button.tsx
│   │       └── Spinner.tsx
│   ├── hooks/
│   │   ├── useSession.ts
│   │   ├── useEventStream.ts
│   │   └── useWorkerStatus.ts
│   ├── api/
│   │   └── client.ts
│   └── types/
│       └── index.ts
└── dist/  # 构建产物
```

### 依赖

- React 18
- TypeScript
- Tailwind CSS
- react-markdown + remark-gfm
- prism-react-renderer (代码高亮)

## UI 细节

### 样式

- **方案**: Tailwind CSS
- **主题**: 深色主题

### 配色

| 元素 | 颜色 |
|------|------|
| 背景 | `#1a1a2e` |
| 卡片 | `#16213e` |
| 强调色 | `#0f4c75` |
| 文字 | `#eaeaea` |
| 用户消息 | 右对齐，蓝色背景 |
| Assistant 消息 | 左对齐，灰色背景 |

### 事件类型颜色

| 事件类型 | 颜色 |
|----------|------|
| `user.message` | 蓝色 |
| `assistant.message` | 绿色 |
| `tool.use` | 黄色 |
| `tool.result` | 灰色 |
| `error` | 红色 |

## 错误处理

### 网络错误

- SSE 断开自动重连（指数退避：1s → 2s → 4s → 最大 30s）
- 显示连接状态指示器

### API 错误

| 错误 | 处理 |
|------|------|
| 会话创建失败 | 弹出错误提示，可重试 |
| 消息发送失败 | 输入框保留内容，显示错误，可重发 |
| 404 会话不存在 | 提示并返回会话列表 |

### 边界情况

| 情况 | 处理 |
|------|------|
| 首次访问无会话 | 自动创建新会话 |
| Worker 离线 | Header 显示红色状态 |
| 长消息 | 虚拟滚动/分页加载 |
