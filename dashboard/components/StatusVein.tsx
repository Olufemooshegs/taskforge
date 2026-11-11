'use client';

const colors: Record<string, string> = {
  queued: 'bg-dim/50',
  running: 'bg-info',
  scheduled: 'bg-warn/70',
  retry_scheduled: 'bg-warn',
  succeeded: 'bg-accent',
  failed: 'bg-danger',
  dead_lettered: 'bg-danger',
  cancelled: 'bg-dim',
};

const pulseable = new Set(['running', 'retry_scheduled']);

export default function StatusVein({ statuses }: { statuses: string[] }) {
  if (!statuses.length) {
    return (
      <div className="h-6 flex items-center text-xs text-dim font-mono">
        no jobs yet
      </div>
    );
  }
  return (
    <div className="flex items-end gap-[2px] h-8">
      {statuses.map((s, i) => (
        <div
          key={i}
          title={s}
          className={`flex-1 min-w-[2px] rounded-sm ${colors[s] || 'bg-dim/40'} ${
            pulseable.has(s) ? 'animate-pulse-dot' : ''
          }`}
          style={{ height: '100%' }}
        />
      ))}
    </div>
  );
}
