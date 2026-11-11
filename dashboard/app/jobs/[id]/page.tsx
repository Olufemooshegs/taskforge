"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import AttemptTimeline from "@/components/AttemptTimeline";
import Card from "@/components/Card";
import LiveDot from "@/components/LiveDot";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import type { JobDetail } from "@/lib/types";

function MetaCell({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-wider text-dim">
        {label}
      </div>
      <div className="mt-0.5 text-xs font-mono text-text break-all">{value}</div>
    </div>
  );
}

function durationOf(job: JobDetail): string {
  if (!job.started_at) return "—";
  const end = job.completed_at ?? job.updated_at;
  const ms = new Date(end).getTime() - new Date(job.started_at).getTime();
  if (ms < 1000) return ms + "ms";
  return (ms / 1000).toFixed(2) + "s";
}

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const {
    data: job,
    error,
    loading,
    setData,
  } = usePolling(() => api.getJob(params.id), 2000);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const canCancel =
    job && ["queued", "scheduled", "retry_scheduled"].includes(job.status);
  const isRunning = job?.status === "running";

  const onCancel = async () => {
    if (!job) return;
    if (!confirm("Cancel this job?")) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const updated = await api.cancelJob(job.id);
      setData(updated as JobDetail);
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading && !job) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-8 w-48 bg-surface/60 rounded" />
        <div className="h-32 bg-surface/60 rounded-lg" />
        <div className="h-64 bg-surface/60 rounded-lg" />
      </div>
    );
  }
  if (error && !job) {
    return (
      <div className="border border-danger/40 bg-danger/10 text-danger rounded-lg p-4 font-mono text-sm">
        FAILED: {error}
      </div>
    );
  }
  if (!job) return null;

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/jobs"
          className="text-xs font-mono text-muted hover:text-accent transition-colors"
        >
          ← jobs
        </Link>
        <div className="flex items-start justify-between mt-2">
          <div>
            <h1 className="text-2xl font-mono font-medium text-text tracking-tight">
              {job.task_name}
            </h1>
            <div className="flex items-center gap-3 mt-2">
              <StatusBadge status={job.status} />
              {isRunning && (
                <span className="flex items-center gap-1.5 text-[11px] font-mono text-info">
                  <LiveDot tone="info" pulse size="xs" />
                  executing
                </span>
              )}
              <span className="text-[11px] font-mono text-dim">
                {job.attempts}/{job.max_attempts} attempts
              </span>
            </div>
          </div>
          {canCancel && (
            <button
              onClick={onCancel}
              disabled={actionLoading}
              className="px-3 py-1.5 rounded border border-danger/40 bg-danger/10 text-danger font-mono text-xs hover:bg-danger/20 disabled:opacity-50 transition-colors"
            >
              {actionLoading ? "cancelling…" : "cancel job"}
            </button>
          )}
        </div>
      </div>

      {actionError && (
        <div className="border border-danger/40 bg-danger/10 text-danger rounded-lg p-3 font-mono text-xs">
          {actionError}
        </div>
      )}

      <div className="border border-border rounded-lg bg-surface/50 grid grid-cols-2 md:grid-cols-4 gap-4 p-4">
        <MetaCell label="job id" value={job.id} />
        <MetaCell label="queue" value={job.queue} />
        <MetaCell
          label="priority"
          value={
            job.priority === 3
              ? "high"
              : job.priority === 2
                ? "normal"
                : "low"
          }
        />
        <MetaCell label="timeout" value={job.timeout_seconds + "s"} />
        <MetaCell
          label="scheduled"
          value={new Date(job.scheduled_at).toLocaleString("en-GB", {
            hour12: false,
          })}
        />
        <MetaCell
          label="started"
          value={
            job.started_at
              ? new Date(job.started_at).toLocaleString("en-GB", {
                  hour12: false,
                })
              : "—"
          }
        />
        <MetaCell
          label="completed"
          value={
            job.completed_at
              ? new Date(job.completed_at).toLocaleString("en-GB", {
                  hour12: false,
                })
              : "—"
          }
        />
        <MetaCell label="total latency" value={durationOf(job)} />
      </div>

      <Card
        title="attempt timeline"
        meta={job.attempt_records.length + " recorded"}
        bodyClassName=""
      >
        <AttemptTimeline attempts={job.attempt_records} />
      </Card>

      {job.last_error && (
        <Card title="last error" bodyClassName="p-4">
          <pre className="text-xs font-mono text-danger/90 whitespace-pre-wrap break-all">
            {job.last_error}
          </pre>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="payload" bodyClassName="p-0">
          <pre className="p-4 text-xs font-mono text-text/90 overflow-x-auto whitespace-pre-wrap break-all">
            {JSON.stringify(job.payload, null, 2)}
          </pre>
        </Card>
        <Card title="result" bodyClassName="p-0">
          {job.result ? (
            <pre className="p-4 text-xs font-mono text-accent/90 overflow-x-auto whitespace-pre-wrap break-all">
              {JSON.stringify(job.result, null, 2)}
            </pre>
          ) : (
            <div className="p-4 text-xs font-mono text-dim">
              no result recorded
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
