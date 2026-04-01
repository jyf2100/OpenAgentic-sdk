import { useState, KeyboardEvent } from 'react';

interface Props {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function InputBox({ onSend, disabled }: Props) {
  const [value, setValue] = useState('');

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !disabled) {
        onSend(value.trim());
        setValue('');
      }
    }
  };

  return (
    <div className="p-4 border-t border-accent/20">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
        disabled={disabled}
        className="w-full bg-card text-text rounded-lg px-4 py-3 resize-none outline-none focus:ring-2 focus:ring-accent/50"
        rows={2}
      />
    </div>
  );
}
