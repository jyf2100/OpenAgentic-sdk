interface Props {
  online: boolean;
  nodeName?: string;
}

export function WorkerIndicator({ online, nodeName }: Props) {
  return (
    <div className="flex items-center gap-2">
      <span
        className={`w-2.5 h-2.5 rounded-full ${
          online ? 'bg-green-500' : 'bg-gray-500'
        }`}
      />
      <span className="text-sm text-text/70">{nodeName || 'worker'}</span>
    </div>
  );
}
