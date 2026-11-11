"use client";

import { useState } from "react";
import type { AttemptRecord } from "@/lib/types";

const DOT: Record<string, string> = {
  succeeded: "bg-accent",
  failed: "bg-danger",
  timed_out: "bg-danger",
  worker_lost: "bg-warn",
  cancelled: "bg-dim",
  running: "bg-info animate-pulse-dot",
};

function fmt(iso: string) {
  return new Date(iso).toLocaleTimeString("en-GB", { hour12: false });
}

function duration(a: AttemptRecord) {
  if (a.duration_ms != null) {
    return a.duration_ms < 1000
      ? a.duration_ms + "ms"
      : (a.duration_ms / 1000).toFixed(2) + "s";
  }
  if (a.finished_at) {
    const ms =
      new Date(a.finished_at).getTime() - new Date(a.started_at).getTime();
    return ms < 1000 ? ms + "ms" : (ms / 1000).toFixed(2) + "s";
  }
  return "running";
}

export default function AttemptTimeline({
  attempts,
}: {
  attempts: AttemptRecord[];
}) {
  const [openTrace, setOpenTrace] = useState<string | null>(null);

  if (!attempts.length) {
    return (
      <div className="px-4 py-6 text-center text-dim font-mono text-[11px]">
        no attempts recorded yet
      </div>
    );
  }

  return (
    <div className="relative pl-6 py-3">
      <div className="absolute left-[19px] top-5 bottom-5 w-px bg-border" />

      {attempts.map((a) => {
        const isOpen = openTrace === a.id;
        const tone =
          a.status === "succeeded"
            ? "text-accent"
            : a.status === "running"
              ? "text-info"
              : "text-danger";
        return (
          <div key={a.id} className="relative pb-4 last:pb-0">
            <span
              className={
                "absolute left-2 top-1.5 w-2.5 h-2.5 rounded-full " +
                (DOT[a.status] || "bg-dim") +
                " ring-4 ring-bg"
              }
            />
            <div className="ml-6">
              <div className="flex items-baseline gap-3 text-[11px] font-mono">
                <span className="text-dim">#{a.attempt_number}</span>
                <span className="text-muted tabular-nums">
                  {fmt(a.started_at)}
                </span>
                <span className="text-dim">→</span>
                <span className="text-muted tabular-nums">
                  {a.finished_at ? fmt(a.finished_at) : "…"}
                </span>
                <span className={"ml-1 " + tone}>{a.status}</span>
                <span className="text-dim ml-auto tabular-nums">
                  {duration(a)}
                </span>
              </div>
              {a.error_type && (
                <div className="mt-1 font-mono text-[11px]">
                  <span className="text-danger">{a.error_type}</span>
                  {a.error_message && (
                    <span className="text-muted"> · {a.error_message}</span>
                  )}
                </div>
              )}
              {a.error_traceback && (
                <button
                  onClick={() => setOpenTrace(isOpen ? null : a.id)}
                  className="mt-1 text-[10px] font-mono text-dim hover:text-accent transition-colors"
                >
                  {isOpen ? "▾ hide traceback" : "▸ show traceback"}
                </button>
              )}
              {isOpen && a.error_traceback && (
                <pre className="mt-2 bg-bg border border-border rounded p-2 text-[10px] font-mono text-danger/90 overflow-x-auto max-h-64 whitespace-pre-wrap break-all">
                  {a.error_traceback}
                </pre>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
