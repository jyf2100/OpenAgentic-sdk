import type { Event } from '../../types';

interface Props {
  events: Event[];
}

export function TokenStats({ events }: Props) {
  const stats = events.reduce(
    (acc, e) => {
      if (e.usage) {
        acc.input += e.usage.input_tokens || 0;
        acc.output += e.usage.output_tokens || 0;
      }
      return acc;
    },
    { input: 0, output: 0 }
  );

  const total = stats.input + stats.output;

  return (
    <div className="p-4">
      <h3 className="text-sm font-medium mb-3">Token 统计</h3>
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-text/70">输入</span>
          <span>{stats.input.toLocaleString()}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-text/70">输出</span>
          <span>{stats.output.toLocaleString()}</span>
        </div>
        <div className="flex justify-between text-sm font-medium pt-2 border-t border-accent/20">
          <span>总计</span>
          <span>{total.toLocaleString()}</span>
        </div>
      </div>
    </div>
  );
}
