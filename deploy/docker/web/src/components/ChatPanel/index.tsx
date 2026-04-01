import { MessageList } from './MessageList';
import { InputBox } from './InputBox';
import type { Message } from '../../types';

interface Props {
  messages: Message[];
  onSend: (message: string) => void;
  sending?: boolean;
}

export function ChatPanel({ messages, onSend, sending }: Props) {
  return (
    <div className="flex flex-col h-full bg-background">
      <MessageList messages={messages} />
      <InputBox onSend={onSend} disabled={sending} />
    </div>
  );
}
