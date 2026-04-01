import { useEffect, useMemo, useState, useCallback } from 'react';
import { Header } from './components/Header';
import { ChatPanel } from './components/ChatPanel';
import { RightPanel } from './components/RightPanel';
import { useSession } from './hooks/useSession';
import { useEventStream } from './hooks/useEventStream';
import { useWorkerStatus } from './hooks/useWorkerStatus';
import { sendMessage as apiSendMessage } from './api/client';
import type { Message } from './types';

export default function App() {
  const { currentSessionId, sessions, createNewSession, switchSession } = useSession();
  const { events, connectionState } = useEventStream(currentSessionId);
  const { status: workerStatus, loading: workerLoading } = useWorkerStatus();

  // 本地待确认消息 (发送后立即显示)
  const [pendingMessages, setPendingMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);

  // 首次访问自动创建会话
  useEffect(() => {
    if (!currentSessionId) {
      createNewSession('新会话');
    }
  }, [currentSessionId, createNewSession]);

  // 从事件提取 assistant 消息 (SSE 不广播 user.message)
  const assistantMessages = useMemo(() => {
    const msgs: Message[] = [];
    for (const e of events) {
      if (e.type === 'assistant.message' && e.text) {
        msgs.push({ role: 'assistant' as const, content: e.text, timestamp: e.ts || Date.now() / 1000 });
      }
    }
    console.log('[App] assistantMessages:', msgs.length);
    return msgs;
  }, [events]);

  // 消息列表：按时间交替排列 user 和 assistant
  // pendingMessages 是用户刚发送的（尚未收到回复）
  // assistantMessages 是收到的 assistant 回复
  const messages = useMemo(() => {
    // 构建消息对：(user, assistant)
    // 假设：每条 pendingMessage 对应一条 assistantMessage（按顺序）
    const result: Message[] = [];
    const pendingCopy = [...pendingMessages].sort((a, b) => a.timestamp - b.timestamp);
    const assistantCopy = [...assistantMessages].sort((a, b) => a.timestamp - b.timestamp);

    // 交替添加：先 user，再 assistant
    const maxLen = Math.max(pendingCopy.length, assistantCopy.length);
    for (let i = 0; i < maxLen; i++) {
      if (i < pendingCopy.length) {
        result.push(pendingCopy[i]);
      }
      if (i < assistantCopy.length) {
        result.push(assistantCopy[i]);
      }
    }

    console.log('[App] final messages:', result.length);
    return result;
  }, [pendingMessages, assistantMessages]);

  // 发送消息
  const handleSend = useCallback(async (prompt: string) => {
    if (!currentSessionId || sending) return;

    // 立即显示用户消息
    const userMsg: Message = {
      role: 'user',
      content: prompt,
      timestamp: Date.now() / 1000,
    };
    setPendingMessages(prev => [...prev, userMsg]);
    setSending(true);

    try {
      await apiSendMessage(currentSessionId, prompt);
    } catch (err) {
      console.error('发送失败:', err);
      // 移除待确认消息
      setPendingMessages(prev => prev.filter(m => m !== userMsg));
    } finally {
      setSending(false);
    }
  }, [currentSessionId, sending]);

  // 当前会话标题
  const currentTitle = sessions.find(s => s.id === currentSessionId)?.metadata?.title || '新会话';

  return (
    <div className="h-screen flex flex-col bg-background text-text">
      <Header
        sessionTitle={currentTitle}
        onRenameSession={(title) => console.log('rename:', title)}
        workerOnline={workerStatus?.ok ?? false}
        workerName={workerStatus?.node_name}
      />
      <div className="flex-1 flex overflow-hidden">
        <div className="w-[60%] border-r border-accent/20">
          <ChatPanel
            messages={messages}
            onSend={handleSend}
            sending={sending || connectionState === 'reconnecting'}
          />
        </div>
        <div className="w-[40%]">
          <RightPanel
            events={events}
            sessions={sessions}
            currentSessionId={currentSessionId}
            onSelectSession={switchSession}
            workerStatus={workerStatus}
            workerLoading={workerLoading}
          />
        </div>
      </div>
    </div>
  );
}
