export type AllocateResp = {
  plan_id: number;
  preset: string;
  summary: {
    requested: number; hostel_beds_used: number; external_beds_used: number;
    review_queue: number; unplaced: number; violations: number; cost: number;
  };
  review_queue: { participant_id: number; raw_id: string | null; reason_code: string; reason: string }[];
  violations: { type: string; participant_id: number; message: string; room_id?: number; external_stay_id?: number }[];
  unplaced: { participant_id: number; raw_id: string | null; reason_code: string; reason: string }[];
  cost: number;
  audit_entry: number;
};

export type Shortage = {
  requested_count: number; hostel_beds_used: number;
  external_beds_used: number; unmet_count: number;
};

export type ReviewQueue = {
  count: number;
  review_queue: { participant_id: number; raw_id: string | null; reason_code: string; reason: string }[];
};

export type Explain = {
  participant_id: number; room_id: number | null; external_stay_id: number | null;
  source: string; reason: string | null; cost: number | null;
  plan_id: number | null; locked: boolean | null;
};
