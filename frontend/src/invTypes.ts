export type InvItem = {
  id: number; sku: string; name: string; category: string | null;
  size: string | null; kind: string | null; condition: string | null; qty: number;
};
export type Levels = { items: InvItem[]; negative: string[] };

export type Shortfall = {
  demand: Record<string, number>;
  stock: Record<string, number>;
  shortfall: Record<string, { needed: number; stock: number; missing: number }>;
  issued_guard: number;
};

export type IssueResp = {
  issue_id: number;
  canonical: string;
  item: { id: number; sku: string; size: string | null };
  audit_entry: number;
};
