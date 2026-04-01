import { WorkerIndicator } from './WorkerIndicator';
import { SessionTitle } from './SessionTitle';

interface Props {
  sessionTitle: string;
  onRenameSession: (title: string) => void;
  workerOnline: boolean;
  workerName?: string;
}

export function Header({ sessionTitle, onRenameSession, workerOnline, workerName }: Props) {
  return (
    <header className="h-14 bg-card border-b border-accent/20 flex items-center justify-between px-4">
      <div className="flex items-center gap-3">
        <span className="text-xl">🤖</span>
        <SessionTitle title={sessionTitle} onRename={onRenameSession} />
      </div>
      <WorkerIndicator online={workerOnline} nodeName={workerName} />
    </header>
  );
}
