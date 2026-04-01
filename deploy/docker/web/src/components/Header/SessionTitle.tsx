import { useState } from 'react';

interface Props {
  title: string;
  onRename: (newTitle: string) => void;
}

export function SessionTitle({ title, onRename }: Props) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(title);

  const handleSubmit = () => {
    if (value.trim() && value !== title) {
      onRename(value.trim());
    }
    setEditing(false);
  };

  if (editing) {
    return (
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={handleSubmit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleSubmit();
          if (e.key === 'Escape') {
            setValue(title);
            setEditing(false);
          }
        }}
        className="bg-card px-2 py-1 rounded text-text outline-none border border-accent"
        autoFocus
      />
    );
  }

  return (
    <h1
      onClick={() => setEditing(true)}
      className="text-lg font-medium cursor-pointer hover:text-accent transition-colors"
    >
      {title || '新会话'}
    </h1>
  );
}
