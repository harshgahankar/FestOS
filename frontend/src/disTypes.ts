export type Report = {
  state_changes: unknown[];
  affected: { count: number; names: string[] };
  new_violations: { type: string; [k: string]: unknown }[];
  suggested_actions: string[];
  cost_delta: number;
};

export type PreviewResp = {
  disruption_id: number;
  type: string;
  report: Report;
  next: string;
};

export type DisruptionRow = {
  id: number;
  type: string;
  status: "previewed" | "applied" | "reverted";
  payload: Record<string, unknown>;
  impact_report: Report | null;
  applied_by: string | null;
  applied_at: string | null;
  has_snapshot: boolean;
};

export type ListResp = { total: number; disruptions: DisruptionRow[] };

export type ActResp = {
  disruption_id: number;
  type: string;
  status: string;
  summary: Record<string, unknown>;
};

export type Venue = {
  id: number;
  raw_id: string;
  name: string;
  capacity: number | null;
};

export const TICKET_TYPES = [
  "late_contingent",
  "duplicate_record",
  "hostel_closure",
  "equipment_failure",
  "venue_change",
  "vendor_shutdown",
  "duplicate_merch_claim",
] as const;
