const styles: Record<string, string> = {
  queued: 'bg-slate-800/50 text-muted border-border',
  running: 'bg-blue-500/10 text-info border-info/30',
  scheduled: 'bg-amber-500/10 text-warn border-warn/30',
  retry_scheduled: 'bg-amber-500/10 text-warn border-warn/30',
  succeeded: 'bg-green-500/10 text-accent border-accent/30',
  failed: 'bg-red-500/10 text-danger border-danger/30',
  dead_lettered: 'bg-red-500/15 text-danger border-danger/40',
  cancelled: 'bg-slate-800/50 text-dim border-border',
};

const labels: Record<string, string> = {
  dead_lettered: 'dead',
  retry_scheduled: 'retry',
  succeeded: 'ok',
};

export default function StatusBadge({ status, dot = true }: { status: string; dot?: boolean }) {
  const cls = styles[status] || 'bg-slate-800/50 text-muted border-border';
  const dotCls: Record<string, string> = {
    queued: 'bg-muted',
    running: 'bg-info animate-pulse-dot',
    scheduled: 'bg-warn',
    retry_scheduled: 'bg-warn animate-pulse-dot',
    succeeded: 'bg-accent',
    failed: 'bg-danger',
    dead_lettered: 'bg-danger',
    cancelled: 'bg-dim',
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-1.5 py-0.5 rounded border text-[11px] font-mono lowercase ${cls}`}
    >
      {dot && <span className={`w-1 h-1 rounded-full ${dotCls[status] || 'bg-muted'}`} />}
      {labels[status] || status}
    </span>
  );
}
