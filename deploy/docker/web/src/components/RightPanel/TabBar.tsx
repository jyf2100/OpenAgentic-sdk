type Tab = 'events' | 'tokens' | 'sessions' | 'worker';

const TABS: { key: Tab; label: string }[] = [
  { key: 'events', label: '事件' },
  { key: 'tokens', label: 'Token' },
  { key: 'sessions', label: '会话' },
  { key: 'worker', label: 'Worker' },
];

interface Props {
  active: Tab;
  onChange: (tab: Tab) => void;
}

export function TabBar({ active, onChange }: Props) {
  return (
    <div className="flex border-b border-accent/20">
      {TABS.map(tab => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={`flex-1 py-2 text-sm transition-colors ${
            active === tab.key
              ? 'text-accent border-b-2 border-accent'
              : 'text-text/50 hover:text-text'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export type { Tab };
