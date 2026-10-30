export type AccessMatrixRow = {
  role: string;
  participants: string;
  accommodation: string;
  events: string;
  logistics: string;
  vendors: string;
  team: string;
  audit: string;
  contact: string;
  medical: string;
  access_room: string;
};

export type TeamMember = {
  id: number;
  raw_id: string;
  name: string;
  role: string;
  original_role?: string;
  shift: string;
  shift_raw?: string;
  shift_crosses_midnight?: boolean;
  contact?: string;
};

export type TeamResponse = {
  access_matrix: AccessMatrixRow[];
  roles: string[];
  shifts: string[];
  shift_details: { key: string; label: string; hours: string }[];
  members: TeamMember[];
  count: number;
};
