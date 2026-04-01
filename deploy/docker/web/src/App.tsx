import { useEffect, useMemo } from 'react';
import { Header } from './components/Header';
import { ChatPanel } from './components/ChatPanel';
import { RightPanel } from './components/RightPanel';
import { useSession } from './hooks/useSession';
import { useEventStream } from './hooks/useEventStream';
import { useWorkerStatus } from './hooks/useWorkerStatus';
import type { Message } from './types';

export default function App() {
  const { currentSessionId, sessions, createNewSession, switchSession } = useSession();
  const { events, connectionState } = useEventStream(currentSessionId);
  const { status: workerStatus, loading: workerLoading } = useWorkerStatus();

  // 首次访问自动创建会话
  useEffect(() => {
    if (!currentSessionId) {
      createNewSession('新会话');
    }
  }, [currentSessionId, createNewSession]);

  // 从事件提取消息
  const messages = useMemo(() => {
    const msgs: Message[] = [];
    for (const e of events) {
      if (e.type === 'user.message' && e.text) {
        msgs.push({ role: 'user', content: e.text, timestamp: e.ts });
      } else if (e.type === 'assistant.message' && e.text) {
        msgs.push({ role: 'assistant', content: e.text, timestamp: e.ts });
      }
    }
    return msgs;
  }, [events]);

  // 发送消息
  const handleSend = async (prompt: string) => {
    if (!currentSessionId) return;
    const { sendMessage } = await import('./api/client');
    await sendMessage(currentSessionId, prompt);
  };

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
            sending={connectionState === 'reconnecting'}
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
