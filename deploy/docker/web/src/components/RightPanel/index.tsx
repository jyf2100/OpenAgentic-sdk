import { useState } from 'react';
import { TabBar } from './TabBar';
import { EventStream } from './EventStream';
import { TokenStats } from './TokenStats';
import { SessionList } from './SessionList';
import { WorkerStatus } from './WorkerStatus';
import type { Event, Session, WorkerStatus as Status } from '../../types';

type Tab = 'events' | 'tokens' | 'sessions' | 'worker';

interface Props {
  events: Event[];
  sessions: Session[];
  currentSessionId: string | null;
  onSelectSession: (id: string) => void;
  workerStatus: Status | null;
  workerLoading: boolean;
}

export function RightPanel({
  events,
  sessions,
  currentSessionId,
  onSelectSession,
  workerStatus,
  workerLoading,
}: Props) {
  const [tab, setTab] = useState<Tab>('events');

  return (
    <div className="flex flex-col h-full bg-background">
      <TabBar active={tab} onChange={setTab} />
      <div className="flex-1 overflow-hidden">
        {tab === 'events' && <EventStream events={events} />}
        {tab === 'tokens' && <TokenStats events={events} />}
        {tab === 'sessions' && (
          <SessionList
            sessions={sessions}
            currentId={currentSessionId}
            onSelect={onSelectSession}
          />
        )}
        {tab === 'worker' && (
          <WorkerStatus status={workerStatus} loading={workerLoading} />
        )}
      </div>
    </div>
  );
}
