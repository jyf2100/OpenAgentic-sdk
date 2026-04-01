import { useState } from 'react';
import type { Event } from '../../types';

interface Props {
  events: Event[];
}

const EVENT_COLORS: Record<string, string> = {
  'user.message': 'text-blue-400',
  'assistant.message': 'text-green-400',
  'tool.use': 'text-yellow-400',
  'tool.result': 'text-gray-400',
  'result': 'text-green-400',
};

export function EventStream({ events }: Props) {
  const [expanded, setExpanded] = useState<number | null>(null);

  const relevantEvents = events.filter(e =>
    ['user.message', 'assistant.message', 'tool.use', 'tool.result', 'result'].includes(e.type)
  );

  return (
    <div className="p-2 overflow-y-auto h-full">
      {relevantEvents.length === 0 ? (
        <div className="text-text/50 text-center py-4 text-sm">暂无事件</div>
      ) : (
        relevantEvents.map((event, idx) => (
          <div
            key={idx}
            className="mb-1 p-2 bg-card rounded cursor-pointer hover:bg-card/80"
            onClick={() => setExpanded(expanded === idx ? null : idx)}
          >
            <div className="flex items-center gap-2">
              <span className="text-xs text-text/50">{event.seq}</span>
              <span className={`text-xs font-mono ${EVENT_COLORS[event.type] || 'text-text'}`}>
                {event.type}
              </span>
            </div>
            {expanded === idx && (
              <pre className="mt-2 text-xs text-text/70 overflow-x-auto">
                {JSON.stringify(event, null, 2)}
              </pre>
            )}
          </div>
        ))
      )}
    </div>
  );
}
