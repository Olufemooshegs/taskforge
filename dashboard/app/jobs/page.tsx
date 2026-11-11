'use client';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import StatusBadge from '@/components/StatusBadge';
import { api } from '@/lib/api';
import { usePolling } from '@/lib/usePolling';
import type { JobListResponse } from '@/lib/types';

const STATUSES = ['queued', 'running', 'scheduled', 'retry_scheduled', 'succeeded', 'failed', 'dead_lettered', 'cancelled'];

export default function JobsPage() {
  const [statuses, setStatuses] = useState<string[]>([]);
  const [queue, setQueue] = useState('');
  const [taskName, setTaskName] = useState('');
  const [cursor, setCursor] = useState<string | null>(null);
  const [page, setPage] = useState<JobListResponse | null>(null);
  const [loadingPage, setLoadingPage] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);

  const qs = useMemo(() => {
    const p = new URLSearchParams();
    statuses.forEach((s) => p.append('status', s));
    if (queue) p.set('queue', queue);
    if (taskName) p.set('task_name', taskName);
    p.set('limit', '25');
    if (cursor) p.set('cursor', cursor);
    return `?${p.toString()}`;
  }, [statuses, queue, taskName, cursor]);

  const { data, error, loading } = usePolling(
    () => api.listJobs(qs),
    3000,
  );

  const goNext = () => { if (data?.next_cursor) { setCursor(data.next_cursor); setPage(null); } };
  const goFirst = () => { setCursor(null); setPage(null); };

  const toggleStatus = (s: string) => {
    setStatuses((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]);
    setCursor(null); setPage(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold">Jobs</h1>
        <span className="text-xs text-slate-500">refreshes every 3s</span>
      </div>

      <div className="bg-white border border-slate-200 rounded p-3 space-y-3">
        <div>
          <div className="text-xs uppercase text-slate-500 mb-1">Status</div>
          <div className="flex flex-wrap gap-1">
            {STATUSES.map((s) => (
              <button
                key={s}
                onClick={() => toggleStatus(s)}
                className={`px-2 py-1 rounded text-xs border ${
                  statuses.includes(s)
                    ? 'bg-slate-900 text-white border-slate-900'
                    : 'bg-white text-slate-700 border-slate-300 hover:border-slate-500'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <label className="text-sm">
            <span className="text-xs uppercase text-slate-500 block mb-1">Queue</span>
            <input
              value={queue}
              onChange={(e) => { setQueue(e.target.value); setCursor(null); setPage(null); }}
              placeholder="e.g. default"
              className="w-full px-2 py-1 border border-slate-300 rounded text-sm"
            />
          </label>
          <label className="text-sm">
            <span className="text-xs uppercase text-slate-500 block mb-1">Task name (exact)</span>
            <input
              value={taskName}
              onChange={(e) => { setTaskName(e.target.value); setCursor(null); setPage(null); }}
              placeholder="e.g. send_welcome_email"
              className="w-full px-2 py-1 border border-slate-300 rounded text-sm"
            />
          </label>
        </div>
      </div>

      {error && !data && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded p-3 text-sm">Failed: {error}</div>
      )}

      {loading && !data && <div className="text-slate-500 text-sm">Loading jobs…</div>}

      {data && (
        <>
          <div className="bg-white border border-slate-200 rounded overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="text-left px-3 py-2">ID</th>
                  <th className="text-left px-3 py-2">Task</th>
                  <th className="text-left px-3 py-2">Queue</th>
                  <th className="text-left px-3 py-2">Status</th>
                  <th className="text-right px-3 py-2">Attempts</th>
                  <th className="text-right px-3 py-2">Priority</th>
                  <th className="text-left px-3 py-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 && (
                  <tr><td colSpan={7} className="text-center text-slate-500 py-8">No jobs match.</td></tr>
                )}
                {data.items.map((j) => (
                  <tr key={j.id} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-3 py-2 font-mono text-xs">
                      <Link href={`/jobs/${j.id}`} className="text-blue-600 hover:underline">
                        {j.id.slice(0, 8)}…
                      </Link>
                    </td>
                    <td className="px-3 py-2">{j.task_name}</td>
                    <td className="px-3 py-2 text-slate-600">{j.queue}</td>
                    <td className="px-3 py-2"><StatusBadge status={j.status} /></td>
                    <td className="px-3 py-2 text-right">{j.attempts}/{j.max_attempts}</td>
                    <td className="px-3 py-2 text-right">{j.priority}</td>
                    <td className="px-3 py-2 text-xs text-slate-500">{j.created_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between text-sm">
            <button
              onClick={goFirst}
              disabled={!cursor}
              className="px-3 py-1 rounded border border-slate-300 disabled:opacity-40"
            >← First page</button>
            <button
              onClick={goNext}
              disabled={!data.next_cursor}
              className="px-3 py-1 rounded border border-slate-300 disabled:opacity-40"
            >Next page →</button>
          </div>
        </>
      )}
    </div>
  );
}
