import type { WorkerStatus as Status, AgentConfig } from '../../types';

interface Props {
  status: Status | null;
  loading: boolean;
}

export function WorkerStatus({ status, loading }: Props) {
  if (loading) return <div className="p-4 text-text/50">加载中...</div>;
  if (!status) return <div className="p-4 text-red-400">Worker 离线</div>;

  const workers = status.workers || {};
  const workerNames = Object.keys(workers);

  return (
    <div className="p-4 overflow-y-auto h-full">
      {/* Host 状态 */}
      <h3 className="text-sm font-medium mb-3">Host 状态</h3>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-text/70">状态</span>
          <span className={status.ok ? 'text-green-400' : 'text-red-400'}>
            {status.ok ? '在线' : '离线'}
          </span>
        </div>
        {status.git_revision && (
          <div className="flex justify-between">
            <span className="text-text/70">Git</span>
            <span className="font-mono text-xs">{status.git_revision.slice(0, 7)}</span>
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

      {/* Workers 列表 */}
      {workerNames.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-medium mb-3">
            Workers ({workerNames.length})
          </h3>
          <div className="space-y-4">
            {workerNames.map(workerName => {
              const agents = workers[workerName] || [];
              return (
                <div key={workerName} className="border border-accent/20 rounded-lg overflow-hidden">
                  {/* Worker 标题 */}
                  <div className="px-3 py-2 bg-accent/10 flex items-center justify-between">
                    <span className="font-medium text-sm">{workerName}</span>
                    <span className="text-xs text-text/50">{agents.length} agents</span>
                  </div>

                  {/* Agents 列表 */}
                  <div className="p-2 space-y-2">
                    {agents.map((agent: AgentConfig) => (
                      <div key={agent.name} className="p-2 bg-card rounded text-sm">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-accent">{agent.name}</span>
                          <span className="text-xs text-text/50">{agent.model}</span>
                        </div>
                        <p className="text-xs text-text/70 mt-1 line-clamp-2">{agent.description}</p>
                        {agent.tools && agent.tools.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {agent.tools.slice(0, 3).map(t => (
                              <span key={t} className="px-1.5 py-0.5 bg-accent/10 rounded text-xs text-text/60">
                                {t}
                              </span>
                            ))}
                            {agent.tools.length > 3 && (
                              <span className="text-xs text-text/50">+{agent.tools.length - 3}</span>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 无 workers 时的提示 */}
      {workerNames.length === 0 && (
        <div className="mt-6 text-center text-text/50 text-sm py-4">
          暂无配置的 Workers
        </div>
      )}
    </div>
  );
}
