import { useEffect, useRef } from 'react';
import { MessageItem } from './MessageItem';
import type { Message } from '../../types';

interface Props {
  messages: Message[];
}

export function MessageList({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {messages.length === 0 ? (
        <div className="text-text/50 text-center py-8">
          开始新对话...
        </div>
      ) : (
        messages.map((msg, idx) => (
          <MessageItem key={idx} message={msg} />
        ))
      )}
      <div ref={bottomRef} />
    </div>
  );
}
