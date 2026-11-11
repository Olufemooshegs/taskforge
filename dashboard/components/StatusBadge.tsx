const styles: Record<string, string> = {
  queued: 'bg-slate-100 text-slate-700',
  running: 'bg-blue-100 text-blue-700',
  scheduled: 'bg-amber-100 text-amber-700',
  retry_scheduled: 'bg-amber-100 text-amber-700',
  succeeded: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  dead_lettered: 'bg-rose-100 text-rose-800',
  cancelled: 'bg-slate-200 text-slate-600',
};

export default function StatusBadge({ status }: { status: string }) {
  const cls = styles[status] || 'bg-slate-100 text-slate-700';
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}
