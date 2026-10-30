export type AttentionItem = {
  source: string;
  severity: "error" | "warning" | "info";
  what: string;
  entity: string;
  action_hint: string;
};

export type AttentionResp = {
  count: number;
  by_severity: Record<string, number>;
  items: AttentionItem[];
};

export type Kpis = {
  participants: { active: number; flagged: number; quarantined: number; linked_duplicates: number; total_rows: number };
  registrations: { rows: number; matched_to_participant: number; issues_open: number };
  occupancy: (Record<string, unknown> & { plan_id: number; preset: string }) | null;
  events: { total: number; scheduled: number; conflicts: number };
  merch: { issued: number; shortfall_sizes: number; missing_units: number };
  vendors: { total: number; expired: number; expiring: number; uncovered_diet_tags: string[] };
};

export type AuditEntry = {
  id: number;
  at: string | null;
  actor: string | null;
  action: string | null;
  kind: string | null;
  entity_type: string | null;
  entity_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  reason: string | null;
};

export type AuditResp = {
  total: number;
  limit: number;
  offset: number;
  entries: AuditEntry[];
};
