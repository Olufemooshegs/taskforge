'use client';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState } from 'react';
import StatusBadge from '@/components/StatusBadge';
import { api } from '@/lib/api';
import { usePolling } from '@/lib/usePolling';
import type { JobDetail } from '@/lib/types';

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const { data: job, error, loading, setData } = usePolling(
    () => api.getJob(params.id),
    2000,
  );
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const canCancel = job && ['queued', 'scheduled', 'retry_scheduled'].includes(job.status);

  const onCancel = async () => {
    if (!job) return;
    if (!confirm('Cancel this job?')) return;
    setActionLoading(true); setActionError(null);
    try {
      const updated = await api.cancelJob(job.id);
      setData(updated as JobDetail);
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading && !job) return <div className="text-slate-500">Loading…</div>;
  if (error && !job) return (
    <div className="bg-red-50 border border-red-200 text-red-800 rounded p-3 text-sm">Failed: {error}</div>
  );
  if (!job) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link href="/jobs" className="text-blue-600 text-sm hover:underline">← Jobs</Link>
        <StatusBadge status={job.status} />
        {canCancel && (
          <button
            onClick={onCancel}
            disabled={actionLoading}
            className="ml-auto px-3 py-1 rounded text-sm bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
          >
            {actionLoading ? 'Cancelling…' : 'Cancel job'}
          </button>
        )}
      </div>

      {actionError && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded p-2 text-sm">{actionError}</div>
      )}

      <h1 className="text-xl font-semibold">{job.task_name}</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 bg-white border border-slate-200 rounded p-3 text-sm">
        <div><div className="text-xs text-slate-500">Job ID</div><div className="font-mono text-xs break-all">{job.id}</div></div>
        <div><div className="text-xs text-slate-500">Queue</div><div>{job.queue}</div></div>
        <div><div className="text-xs text-slate-500">Attempts</div><div>{job.attempts}/{job.max_attempts}</div></div>
        <div><div className="text-xs text-slate-500">Priority</div><div>{job.priority}</div></div>
        <div><div className="text-xs text-slate-500">Created</div><div className="text-xs">{job.created_at}</div></div>
        <div><div className="text-xs text-slate-500">Scheduled</div><div className="text-xs">{job.scheduled_at}</div></div>
        <div><div className="text-xs text-slate-500">Started</div><div className="text-xs">{job.started_at ?? '—'}</div></div>
        <div><div className="text-xs text-slate-500">Completed</div><div className="text-xs">{job.completed_at ?? '—'}</div></div>
      </div>

      {job.last_error && (
        <div className="bg-red-50 border border-red-200 rounded p-3">
          <div className="text-xs text-red-800 uppercase mb-1">Last error</div>
          <pre className="text-xs text-red-900 whitespace-pre-wrap break-all">{job.last_error}</pre>
        </div>
      )}

      <div>
        <h2 className="text-sm font-medium text-slate-700 mb-1">Payload</h2>
        <pre className="bg-slate-900 text-slate-100 rounded p-3 text-xs overflow-x-auto">
{JSON.stringify(job.payload, null, 2)}
        </pre>
      </div>

      <div>
        <h2 className="text-sm font-medium text-slate-700 mb-1">Result</h2>
        {job.result ? (
          <pre className="bg-slate-900 text-slate-100 rounded p-3 text-xs overflow-x-auto">
{JSON.stringify(job.result, null, 2)}
          </pre>
        ) : (
          <p className="text-slate-500 text-sm">No result recorded.</p>
        )}
      </div>
    </div>
  );
}
