import type { Session } from '../../types';

interface Props {
  sessions: Session[];
  currentId: string | null;
  onSelect: (id: string) => void;
}

export function SessionList({ sessions, currentId, onSelect }: Props) {
  return (
    <div className="p-2 overflow-y-auto h-full">
      {sessions.length === 0 ? (
        <div className="text-text/50 text-center py-4 text-sm">暂无会话</div>
      ) : (
        sessions.map(session => (
          <div
            key={session.id}
            onClick={() => onSelect(session.id)}
            className={`p-3 rounded cursor-pointer mb-1 ${
              currentId === session.id
                ? 'bg-accent/20 border border-accent/40'
                : 'bg-card hover:bg-card/80'
            }`}
          >
            <div className="text-sm truncate">
              {session.metadata?.title || '新会话'}
            </div>
            <div className="text-xs text-text/50 mt-1">
              {new Date(session.created_at * 1000).toLocaleString()}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
