export type SchedEvent = {
  id: number;
  raw_id: string;
  name: string;
  type: string | null;
  rounds: unknown[];
  duration_minutes: number | null;
  venue_id: number | null;
  start: string | null;
  end: string | null;
  registration_count: number;
};
export type EventsList = { total: number; events: SchedEvent[] };

export type Conflict = {
  type: string;
  severity: "error" | "warning" | "info";
  message: string;
  venue?: number;
  event?: string;
  event_1?: string;
  event_2?: string;
  actor?: string;
  core_team_id?: number;
  sku?: string;
  day?: string;
};
export type ConflictCheck = {
  conflicts: Conflict[];
  suggestions: string[];
  checked_events: number;
  summary: Record<string, number>;
};

export type EditResp = {
  event_id: number;
  raw_id: string;
  changed: string[];
  audit_entry: number;
  post_edit_conflicts: number;
  conflicts_involved: Conflict[];
};

export type MoveResp = {
  event_id: number;
  raw_id: string;
  audit_entry: number;
  remaining_conflicts_for_event: Conflict[];
  suggestions: string[];
};
