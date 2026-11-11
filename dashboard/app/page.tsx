"use client";

import Link from "next/link";
import Card from "@/components/Card";
import CountTick from "@/components/CountTick";
import LiveDot from "@/components/LiveDot";
import Sparkline from "@/components/Sparkline";
import StatusBadge from "@/components/StatusBadge";
import StatusVein from "@/components/StatusVein";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import type { Event, EventsResponse } from "@/lib/types";

function StatBlock({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: number;
  sub?: string;
  tone?: "default" | "good" | "warn" | "bad" | "info";
}) {
  const tones = {
    default: "text-text",
    good: "text-accent",
    warn: "text-warn",
    bad: "text-danger",
    info: "text-info",
  };
  return (
    <div className="border border-border rounded-lg bg-surface/50 p-4">
      <div className="text-[11px] font-mono uppercase tracking-wider text-muted">
        {label}
      </div>
      <div className={"text-3xl font-mono font-medium mt-1 " + tones[tone]}>
        <CountTick value={value} />
      </div>
      {sub && (
        <div className="text-[11px] font-mono text-dim mt-1">{sub}</div>
      )}
    </div>
  );
}

const EVENT_STYLE: Record<string, { color: string; verb: string }> = {
  claimed: { color: "text-info", verb: "claimed" },
  succeeded: { color: "text-accent", verb: "succeeded" },
  failed: { color: "text-danger", verb: "failed" },
  timed_out: { color: "text-danger", verb: "timed out" },
  worker_lost: { color: "text-warn", verb: "worker lost" },
};

export default function OverviewPage() {
  const { data: stats, error, loading } = usePolling(
    () => api.overview(),
    3000
  );
  const { data: recentJobs } = usePolling(
    () => api.listJobs("?limit=8"),
    3000
  );
  const { data: eventsData } = usePolling<EventsResponse>(
    () => fetch("/api/tf/events/recent?limit=12").then((r) => r.json()),
    2000
  );

  if (loading && !stats) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-24 bg-surface/60 rounded-lg" />
        <div className="grid grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-24 bg-surface/60 rounded-lg" />
          ))}
        </div>
        <div className="h-64 bg-surface/60 rounded-lg" />
      </div>
    );
  }
  if (error && !stats) {
    return (
      <div className="border border-danger/40 bg-danger/10 text-danger rounded-lg p-4 font-mono text-sm">
        FAILED TO LOAD: {error}
      </div>
    );
  }
  if (!stats) return null;

  const {
    jobs,
    workers,
    queues,
    recent_failures,
    status_vein,
    throughput_60s,
  } = stats;
  const events: Event[] = eventsData?.items ?? [];
  const total = jobs.total;
  const succeededPct = total ? ((jobs.succeeded / total) * 100).toFixed(1) : "0.0";
  const deadPct = total ? ((jobs.dead_lettered / total) * 100).toFixed(1) : "0.0";
  const throughputNow =
    throughput_60s.slice(-10).reduce((a, b) => a + b, 0) / 10;

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-mono font-medium text-text tracking-tight">
            Overview
          </h1>
          <p className="text-sm text-muted mt-1">
            Live snapshot · polling every 3s
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5 text-muted">
            <LiveDot
              tone={workers.live > 0 ? "good" : "bad"}
              pulse={workers.live > 0}
            />
            <span>
              {workers.live}/{workers.total} workers
            </span>
          </div>
          <span className="text-dim">|</span>
          <span className="text-dim">{throughputNow.toFixed(2)} jobs/s</span>
        </div>
      </div>

      <Card title="throughput" meta="last 60 seconds" bodyClassName="p-4">
        <div className="flex items-baseline justify-between mb-2">
          <div className="font-mono">
            <span className="text-2xl text-accent">
              {throughputNow.toFixed(2)}
            </span>
            <span className="text-sm text-muted ml-1">jobs/s</span>
          </div>
          <span className="text-xs text-dim font-mono">60s window</span>
        </div>
        <Sparkline data={throughput_60s} height={72} className="w-full" />
      </Card>

      <Card
        title="status vein"
        meta={"last " + status_vein.length + " jobs"}
        bodyClassName="px-4 py-4"
      >
        <StatusVein statuses={status_vein} />
        <div className="flex items-center gap-4 mt-3 text-[10px] font-mono text-dim">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 bg-accent rounded-sm" />
            ok
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 bg-info rounded-sm" />
            running
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 bg-warn rounded-sm" />
            retry
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 bg-danger rounded-sm" />
            dead
          </span>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <StatBlock
              label="succeeded"
              value={jobs.succeeded}
              sub={succeededPct + "% of all"}
              tone="good"
            />
            <StatBlock
              label="running"
              value={jobs.running}
              sub="in-flight"
              tone="info"
            />
            <StatBlock
              label="dead lettered"
              value={jobs.dead_lettered}
              sub={deadPct + "% of all"}
              tone="bad"
            />
          </div>

          <Card title="recent jobs" meta="latest 8" bodyClassName="">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-mono uppercase text-dim border-b border-border">
                  <th className="text-left px-4 py-2 font-normal">id</th>
                  <th className="text-left px-4 py-2 font-normal">task</th>
                  <th className="text-left px-4 py-2 font-normal">status</th>
                  <th className="text-right px-4 py-2 font-normal">attempts</th>
                  <th className="text-right px-4 py-2 font-normal">latency</th>
                </tr>
              </thead>
              <tbody>
                {(recentJobs?.items ?? []).map((j) => (
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
                    <td className="px-4 py-2">
                      <StatusBadge status={j.status} />
                    </td>
                    <td className="px-4 py-2 text-right font-mono text-xs text-muted">
                      {j.attempts}/{j.max_attempts}
                    </td>
                    <td className="px-4 py-2 text-right font-mono text-xs text-dim">
                      {j.started_at
                        ? (() => {
                            const end = j.completed_at ?? j.updated_at;
                            const ms =
                              new Date(end).getTime() -
                              new Date(j.started_at).getTime();
                            return ms < 1000
                              ? ms + "ms"
                              : (ms / 1000).toFixed(1) + "s";
                          })()
                        : "—"}
                    </td>
                  </tr>
                ))}
                {(!recentJobs || recentJobs.items.length === 0) && (
                  <tr>
                    <td
                      colSpan={5}
                      className="text-center py-8 text-dim font-mono text-xs"
                    >
                      no jobs yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </Card>

          {recent_failures.length > 0 && (
            <Card
              title="recent failures"
              meta={String(recent_failures.length)}
              bodyClassName=""
            >
              <div className="divide-y divide-border/40">
                {recent_failures.map((f) => (
                  <Link
                    key={f.id}
                    href={"/jobs/" + f.id}
                    className="block px-4 py-2.5 hover:bg-surface-hi/50 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <StatusBadge status={f.status} />
                      <span className="font-mono text-xs text-text">
                        {f.task_name}
                      </span>
                      <span className="ml-auto font-mono text-[10px] text-dim">
                        {new Date(f.updated_at).toLocaleTimeString("en-GB", {
                          hour12: false,
                        })}
                      </span>
                    </div>
                    {f.last_error && (
                      <div className="font-mono text-[11px] text-danger/80 truncate mt-1">
                        {f.last_error}
                      </div>
                    )}
                  </Link>
                ))}
              </div>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card title="queues" bodyClassName="">
            <div className="divide-y divide-border/40">
              {queues.map((q) => (
                <div key={q.id} className="px-4 py-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm text-text">{q.name}</span>
                    <span
                      className={
                        "text-[10px] font-mono uppercase " +
                        (q.is_active ? "text-accent" : "text-dim")
                      }
                    >
                      {q.is_active ? "active" : "off"}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-[11px] font-mono text-dim">
                    <span>{q.running} running</span>
                    <span>·</span>
                    <span>{q.queued} queued</span>
                    {q.retry_scheduled > 0 && (
                      <>
                        <span>·</span>
                        <span className="text-warn">
                          {q.retry_scheduled} retry
                        </span>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card
            title="live events"
            meta={events.length ? "· " + events.length : ""}
            action={<LiveDot tone="good" pulse size="xs" />}
            bodyClassName=""
          >
            <div className="max-h-96 overflow-y-auto">
              {events.length === 0 && (
                <div className="px-4 py-6 text-center text-dim font-mono text-[11px]">
                  waiting for activity…
                </div>
              )}
              <div className="divide-y divide-border/40">
                {events.map((e) => {
                  const st = EVENT_STYLE[e.kind] || EVENT_STYLE.claimed;
                  return (
                    <div key={e.id} className="px-4 py-2 animate-fade-in">
                      <div className="flex items-center gap-2 text-[11px] font-mono">
                        <span className="text-dim tabular-nums">
                          {new Date(e.at).toLocaleTimeString("en-GB", {
                            hour12: false,
                          })}
                        </span>
                        <span className={st.color}>{st.verb}</span>
                        <Link
                          href={"/jobs/" + e.job_id}
                          className="text-muted hover:text-accent truncate"
                        >
                          {e.task_name}
                        </Link>
                        <span className="text-dim ml-auto">
                          #{e.attempt_number}
                        </span>
                      </div>
                      {e.detail && (
                        <div className="text-[10px] text-danger/70 font-mono truncate mt-0.5">
                          {e.detail}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
