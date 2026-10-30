export type ParticipantView = {
  id: number;
  raw_id: string;
  name: string;
  college: string | null;
  contingent: string | null;
  gender: string | null;
  age: number | null;
  phone: string | number | null;
  email: string | null;
  accessibility_status: string | null;
  accessibility_details: string | null;
  dietary_status: string | null;
  dietary_tags: string[] | null;
  medical_notes: string | null;
  tshirt_size: string | null;
  arrival: string | null;
  departure: string | null;
  accommodation_requested: string | null;
  status: string;
  merged_into: number | null;
  quality_flags: string[];
  room?: string | null;
};

export type PeopleList = {
  total: number; limit: number; offset: number;
  participants: ParticipantView[];
};

export type Cluster = {
  canonical: { id: number; raw_id: string | null; name: string | null };
  duplicates: { id: number; raw_id: string; name: string | null; quality_flags: string[] }[];
};
export type DuplicatesResp = { clusters: Cluster[]; count: number };

export type Participant360 = {
  participant: ParticipantView;
  contingent: {
    raw_id: string; college: string | null; leader: string | null; escort: string | null;
    size_declared: number | null; size_actual: number | null; preferences: string[];
  } | null;
  events: { event_id: string; role: string | null; team_id: string | null; status: string | null }[];
  bed: string | null;
  merch_issued: { item_id: string; at: string }[];
  audit: { at: string; actor: string | null; kind: string | null; reason: string | null }[];
};

export type ContigView = {
  id: number; raw_id: string; college: string | null; name: string | null;
  leader: string | null; escort: string | null; escort_count: number | null;
  size_declared: number | null; size_actual: number | null; size_mismatch: number | null;
  arrival_window: Record<string, unknown>; preferences: string[];
};
export type ContigList = { total: number; limit: number; offset: number; contingents: ContigView[] };

export type ContigDetail = {
  contingent: ContigView & { leader_participant_id: number | null; preferences_raw: string | null };
  member_count: number;
  members: ParticipantView[];
  arrival_days: string[];
  departure_days: string[];
  open_issues: { code: string; severity: string; message: string }[];
};
