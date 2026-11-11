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
  status_vein: string[];
  throughput_60s: number[];
}

export interface JobSummary {
  id: string;
  queue: string;
  task_name: string;
  status: string;
  priority: number;
  attempts: number;
  max_attempts: number;
  scheduled_at: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AttemptRecord {
  id: string;
  attempt_number: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  error_type: string | null;
  error_message: string | null;
  error_traceback: string | null;
}

export interface JobDetail extends JobSummary {
  tenant_id: string;
  queue_id: string;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
  last_error: string | null;
  timeout_seconds: number;
  attempt_records: AttemptRecord[];
}

export interface JobListResponse {
  items: JobSummary[];
  next_cursor: string | null;
}

export interface Event {
  id: string;
  kind: 'claimed' | 'succeeded' | 'failed' | 'timed_out' | 'worker_lost' | string;
  job_id: string;
  task_name: string;
  attempt_number: number;
  at: string;
  detail: string | null;
  worker_hostname: string | null;
}
export interface EventsResponse { items: Event[]; }
