import type { WorkerStatus as Status } from '../../types';

interface Props {
  status: Status | null;
  loading: boolean;
}

export function WorkerStatus({ status, loading }: Props) {
  if (loading) return <div className="p-4 text-text/50">加载中...</div>;
  if (!status) return <div className="p-4 text-red-400">Worker 离线</div>;

  return (
    <div className="p-4">
      <h3 className="text-sm font-medium mb-3">Worker 状态</h3>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-text/70">状态</span>
          <span className={status.ok ? 'text-green-400' : 'text-red-400'}>
            {status.ok ? '在线' : '离线'}
          </span>
        </div>
        {status.node_name && (
          <div className="flex justify-between">
            <span className="text-text/70">节点</span>
            <span>{status.node_name}</span>
          </div>
        )}
        {status.provider_ready !== undefined && (
          <div className="flex justify-between">
            <span className="text-text/70">Provider</span>
            <span className={status.provider_ready ? 'text-green-400' : 'text-red-400'}>
              {status.provider_ready ? '就绪' : '未就绪'}
            </span>
          </div>
        )}
        {status.provider_profiles && (
          <div className="mt-2">
            <span className="text-text/70">Providers:</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {status.provider_profiles.map(p => (
                <span key={p} className="px-2 py-0.5 bg-accent/20 rounded text-xs">{p}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
