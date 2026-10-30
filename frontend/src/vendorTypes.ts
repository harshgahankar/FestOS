export type Vendor = {
  id: number;
  raw_id: string;
  name: string;
  dietary_coverage: string[];
  hygiene_cert_expiry: string | null;
  capacity_per_day: number | null;
  rate: number | null;
  status: string;
};

export type VendorsList = {
  days: { start: string; end: string };
  vendors: Vendor[];
  compliance: { expired: string[]; expiring: string[] };
};

export type Coverage = {
  tags_with_players: string[];
  matrix: Record<string, { demand: number; vendors: number[]; unmet: number }>;
  uncovered_tags: string[];
};

export type SettlementRow = {
  vendor_id: number;
  raw_id: string;
  name: string;
  orders: number;
  qty: number;
  rate: number | null;
  amount: number | null;
  paid: boolean;
  needs_manual_entry: boolean;
  notes: string[];
};

export type Settlement = {
  rows: SettlementRow[];
  total_estimated: number;
  pending_entries: string[];
};

export type PreviewResp = {
  vendor_id: number;
  moves: { order: number; day: string; meal: string; dietary_tag: string | null; to_vendor: number; to_vendor_raw_id: string }[];
  unmet: { order: number; day: string; meal: string; dietary_tag: string | null; reason: string }[];
};

export type ApplyResp = {
  vendor_id: number;
  status: string;
  orders_moved: number;
  unmet: PreviewResp["unmet"];
};
