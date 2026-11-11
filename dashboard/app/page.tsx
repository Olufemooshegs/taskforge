'use client';
import Link from 'next/link';
import StatCard from '@/components/StatCard';
import StatusBadge from '@/components/StatusBadge';
import { api } from '@/lib/api';
import { usePolling } from '@/lib/usePolling';

export default function OverviewPage() {
  const { data, error, loading } = usePolling(() => api.overview(), 3000);

  if (loading && !data) return <div className="text-slate-500">Loading overview…</div>;
  if (error && !data) return (
    <div className="bg-red-50 border border-red-200 text-red-800 rounded p-4">
      Failed to load overview: {error}
    </div>
  );
  if (!data) return null;

  const { jobs, workers, queues, recent_failures } = data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Overview</h1>
        <p className="text-sm text-slate-500">Live snapshot — refreshes every 3s</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Total jobs" value={jobs.total} />
        <StatCard label="Queued" value={jobs.queued + jobs.retry_scheduled} hint={`${jobs.retry_scheduled} awaiting retry`} />
        <StatCard label="Running" value={jobs.running} tone={jobs.running > 0 ? 'warn' : 'default'} />
        <StatCard label="Workers" value={`${workers.live}/${workers.total}`} hint="live / registered" tone={workers.live > 0 ? 'good' : 'bad'} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Succeeded" value={jobs.succeeded} tone="good" />
        <StatCard label="Failed" value={jobs.failed} tone={jobs.failed > 0 ? 'warn' : 'default'} />
        <StatCard label="Dead lettered" value={jobs.dead_lettered} tone={jobs.dead_lettered > 0 ? 'bad' : 'default'} />
        <StatCard label="Cancelled" value={jobs.cancelled} />
      </div>

      <div>
        <h2 className="text-lg font-medium mb-2">Queues</h2>
        {queues.length === 0 ? (
          <p className="text-slate-500 text-sm">No queues configured.</p>
        ) : (
          <div className="bg-white border border-slate-200 rounded overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="text-left px-3 py-2">Name</th>
                  <th className="text-right px-3 py-2">Queued</th>
                  <th className="text-right px-3 py-2">Running</th>
                  <th className="text-right px-3 py-2">Retry</th>
                  <th className="text-right px-3 py-2">Max concurrency</th>
                  <th className="text-center px-3 py-2">Active</th>
                </tr>
              </thead>
              <tbody>
                {queues.map((q) => (
                  <tr key={q.id} className="border-t border-slate-100">
                    <td className="px-3 py-2 font-medium">{q.name}</td>
                    <td className="px-3 py-2 text-right">{q.queued}</td>
                    <td className="px-3 py-2 text-right">{q.running}</td>
                    <td className="px-3 py-2 text-right">{q.retry_scheduled}</td>
                    <td className="px-3 py-2 text-right">{q.max_concurrency}</td>
                    <td className="px-3 py-2 text-center">{q.is_active ? '✅' : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div>
        <h2 className="text-lg font-medium mb-2">Recent failures</h2>
        {recent_failures.length === 0 ? (
          <p className="text-slate-500 text-sm">No failures.</p>
        ) : (
          <div className="bg-white border border-slate-200 rounded divide-y divide-slate-100">
            {recent_failures.map((f) => (
              <Link key={f.id} href={`/jobs/${f.id}`} className="block px-3 py-2 hover:bg-slate-50">
                <div className="flex items-center gap-2">
                  <StatusBadge status={f.status} />
                  <span className="font-medium text-sm">{f.task_name}</span>
                  <span className="text-xs text-slate-400 ml-auto">{f.updated_at}</span>
                </div>
                {f.last_error && <div className="text-xs text-red-700 truncate mt-1">{f.last_error}</div>}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
