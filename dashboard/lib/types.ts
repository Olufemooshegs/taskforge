export interface JobCounts {
  total: number;
  queued: number;
  running: number;
  scheduled: number;
  retry_scheduled: number;
  succeeded: number;
  failed: number;
  dead_lettered: number;
  cancelled: number;
}

export interface WorkerCounts { total: number; active: number; live: number; }
export interface QueueStat {
  id: string; name: string; is_active: boolean; max_concurrency: number;
  queued: number; running: number; retry_scheduled: number;
}
export interface RecentFailure {
  id: string; task_name: string; status: string;
  last_error: string | null; updated_at: string;
}
export interface OverviewStats {
  jobs: JobCounts;
  workers: WorkerCounts;
  queues: QueueStat[];
  recent_failures: RecentFailure[];
}

export interface JobSummary {
  id: string; queue: string; task_name: string; status: string;
  priority: number; attempts: number; max_attempts: number;
  scheduled_at: string; created_at: string; updated_at: string;
}
export interface JobDetail extends JobSummary {
  tenant_id: string; queue_id: string;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
  started_at: string | null; completed_at: string | null;
  last_error: string | null; timeout_seconds: number;
}
export interface JobListResponse { items: JobSummary[]; next_cursor: string | null; }
