"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import Card from "@/components/Card";
import LiveDot from "@/components/LiveDot";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import type { JobSummary } from "@/lib/types";

const STATUSES = [
  "queued",
  "running",
  "scheduled",
  "retry_scheduled",
  "succeeded",
  "failed",
  "dead_lettered",
  "cancelled",
];

function rowLatency(j: JobSummary): string {
  if (!j.started_at) return "—";
  const end = j.completed_at ?? j.updated_at;
  const ms = new Date(end).getTime() - new Date(j.started_at).getTime();
  if (ms < 1000) return ms + "ms";
  return (ms / 1000).toFixed(1) + "s";
}

export default function JobsPage() {
  const [statuses, setStatuses] = useState<string[]>([]);
  const [queue, setQueue] = useState("");
  const [taskName, setTaskName] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);

  const qs = useMemo(() => {
    const p = new URLSearchParams();
    statuses.forEach((s) => p.append("status", s));
    if (queue) p.set("queue", queue);
    if (taskName) p.set("task_name", taskName);
    p.set("limit", "25");
    if (cursor) p.set("cursor", cursor);
    return "?" + p.toString();
  }, [statuses, queue, taskName, cursor]);

  const { data, error, loading } = usePolling(() => api.listJobs(qs), 3000);

  const toggleStatus = (s: string) => {
    setStatuses((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );
    setCursor(null);
  };

  const clearAll = () => {
    setStatuses([]);
    setQueue("");
    setTaskName("");
    setCursor(null);
  };

  const hasFilters = statuses.length > 0 || queue || taskName || cursor;

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-mono font-medium text-text tracking-tight">
            Jobs
          </h1>
          <p className="text-sm text-muted mt-1">
            {data ? data.items.length + " shown" : "loading…"}
            {hasFilters && (
              <button
                onClick={clearAll}
                className="ml-3 text-accent hover:underline font-mono"
              >
                clear filters
              </button>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-muted">
          <LiveDot tone="good" pulse size="xs" />
          <span>refreshing every 3s</span>
        </div>
      </div>

      <div className="border border-border rounded-lg bg-surface/50 p-4 space-y-3">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-wider text-muted mb-2">
            status
          </div>
          <div className="flex flex-wrap gap-1.5">
            {STATUSES.map((s) => {
              const active = statuses.includes(s);
              return (
                <button
                  key={s}
                  onClick={() => toggleStatus(s)}
                  className={
                    "px-2 py-1 rounded text-[11px] font-mono border transition-colors " +
                    (active
                      ? "bg-accent text-bg border-accent"
                      : "bg-surface text-muted border-border hover:border-border-hi hover:text-text")
                  }
                >
                  {s}
                </button>
              );
            })}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label>
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted mb-1">
              queue
            </div>
            <input
              value={queue}
              onChange={(e) => {
                setQueue(e.target.value);
                setCursor(null);
              }}
              placeholder="e.g. default"
              className="w-full px-3 py-1.5 bg-bg border border-border rounded font-mono text-xs text-text placeholder:text-dim focus:outline-none focus:border-border-hi"
            />
          </label>
          <label>
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted mb-1">
              task name (exact)
            </div>
            <input
              value={taskName}
              onChange={(e) => {
                setTaskName(e.target.value);
                setCursor(null);
              }}
              placeholder="e.g. send_welcome_email"
              className="w-full px-3 py-1.5 bg-bg border border-border rounded font-mono text-xs text-text placeholder:text-dim focus:outline-none focus:border-border-hi"
            />
          </label>
        </div>
      </div>

      {error && !data && (
        <div className="border border-danger/40 bg-danger/10 text-danger rounded-lg p-4 font-mono text-sm">
          FAILED: {error}
        </div>
      )}

      <Card bodyClassName="">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] font-mono uppercase text-dim border-b border-border">
              <th className="text-left px-4 py-2.5 font-normal">id</th>
              <th className="text-left px-4 py-2.5 font-normal">task</th>
              <th className="text-left px-4 py-2.5 font-normal">queue</th>
              <th className="text-left px-4 py-2.5 font-normal">status</th>
              <th className="text-right px-4 py-2.5 font-normal">attempts</th>
              <th className="text-right px-4 py-2.5 font-normal">latency</th>
              <th className="text-right px-4 py-2.5 font-normal">prio</th>
              <th className="text-right px-4 py-2.5 font-normal">created</th>
            </tr>
          </thead>
          <tbody>
            {loading && !data && (
              <tr>
                <td
                  colSpan={8}
                  className="text-center py-12 text-dim font-mono text-xs"
                >
                  loading jobs…
                </td>
              </tr>
            )}
            {data && data.items.length === 0 && (
              <tr>
                <td
                  colSpan={8}
                  className="text-center py-12 text-dim font-mono text-xs"
                >
                  no jobs match these filters
                </td>
              </tr>
            )}
            {data?.items.map((j) => (
              <tr
                key={j.id}
                className="border-b border-border/40 hover:bg-surface-hi/50 transition-colors"
              >
                <td className="px-4 py-2 font-mono text-xs">
                  <Link
                    href={"/jobs/" + j.id}
                    className="text-muted hover:text-accent"
                  >
                    {j.id.slice(0, 8)}
                  </Link>
                </td>
                <td className="px-4 py-2 font-mono text-xs text-text">
                  {j.task_name}
                </td>
                <td className="px-4 py-2 font-mono text-xs text-muted">
                  {j.queue}
                </td>
                <td className="px-4 py-2">
                  <StatusBadge status={j.status} />
                </td>
                <td className="px-4 py-2 text-right font-mono text-xs text-muted">
                  {j.attempts}/{j.max_attempts}
                </td>
                <td className="px-4 py-2 text-right font-mono text-xs text-dim">
                  {rowLatency(j)}
                </td>
                <td className="px-4 py-2 text-right font-mono text-xs text-muted">
                  {j.priority === 3 ? "H" : j.priority === 2 ? "N" : "L"}
                </td>
                <td className="px-4 py-2 text-right font-mono text-[10px] text-dim">
                  {new Date(j.created_at).toLocaleTimeString("en-GB", {
                    hour12: false,
                  })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <div className="flex items-center justify-between text-xs font-mono">
        <button
          onClick={() => setCursor(null)}
          disabled={!cursor}
          className="px-3 py-1.5 rounded border border-border bg-surface text-muted hover:text-text hover:border-border-hi disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          ← first page
        </button>
        <span className="text-dim">{cursor ? "page 2+" : "page 1"}</span>
        <button
          onClick={() => {
            if (data?.next_cursor) setCursor(data.next_cursor);
          }}
          disabled={!data?.next_cursor}
          className="px-3 py-1.5 rounded border border-border bg-surface text-muted hover:text-text hover:border-border-hi disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          next page →
        </button>
      </div>
    </div>
  );
}
