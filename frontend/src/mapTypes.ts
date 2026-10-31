import type { Role } from "./auth";

export type MapTone = "teal" | "gold" | "maroon" | "grey" | string;

export type MapStatus = {
  code: string;
  label: string;
  tone: MapTone;
  color: MapTone;
};

export type MapLink = {
  entity_type: string;
  entity_id: string;
  label: string;
};

export type MapTarget = {
  entity_type: string;
  entity_id: string;
  name: string;
  location_id?: number;
};

export type MapIncident = {
  id: number;
  type: string;
  status: string;
  effect: "verified" | "potential";
  verified: boolean;
  applied_at: string | null;
  applied_by: string | null;
  targets: MapTarget[];
  location_ids: number[];
  impact_summary: {
    affected: number;
    violations: number;
    cost_delta: number | null;
  };
  recovery: Record<string, unknown> | null;
};

export type MapEvent = {
  id: number;
  raw_id: string;
  name: string;
  type: string | null;
  start: string | null;
  end: string | null;
  status: "ongoing" | "upcoming" | "completed";
  conflicts: Record<string, unknown>[];
  registration_count: number;
  rounds: string[];
  equipment_needs?: unknown[];
  volunteers_needed?: number;
  staff?: { name: string; role: string | null }[];
};

export type MapAllocation = {
  allocation_id: number;
  source: string | null;
  person: {
    raw_id: string;
    name: string;
    accessibility_status: string | null;
    accessibility_details: string | null;
  } | null;
};

export type MapRoom = {
  id: number;
  raw_id: string;
  floor: number | null;
  room_no: string | null;
  beds: number;
  allocated: number;
  vacant: number;
  accessible: boolean;
  gender_block: string | null;
  readiness: string;
  status: string;
  allocation_status: string;
  allocations?: MapAllocation[];
};

export type MapFloor = {
  floor: number;
  rooms: number;
  beds: number;
  allocated: number;
  vacant: number;
  accessible_rooms: number;
};

export type MapItem = {
  id: number;
  sku: string;
  name: string;
  category: string | null;
  kind: string;
  condition: string | null;
  on_hand: number;
  available: number;
  reserved: number;
  under_repair: number;
  global_available: number;
};

export type MapMovement = {
  id: number;
  at: string | null;
  item_id: number;
  sku: string | null;
  name: string | null;
  qty: number;
  from_location: string | null;
  to_location: string | null;
  status: string | null;
  reference: string | null;
};

export type MapContext = {
  kind?: string;
  status?: MapStatus;
  summary?: Record<string, unknown>;
  name?: string;
  block?: string;
  property?: string;
  label?: string;
  total_beds?: number;
  allocated_beds?: number;
  vacant_beds?: number;
  unavailable_beds?: number;
  occupancy_pct?: number | null;
  rooms_total?: number;
  ready_rooms?: number;
  accessible_rooms?: number;
  accessible_beds?: number;
  floors?: MapFloor[];
  rooms?: MapRoom[];
  beds?: number;
  distance_km?: number | null;
  travel_minutes?: number | null;
  transport_available?: string | null;
  safety_coverage?: string | null;
  capacity?: number | null;
  venue_status?: string;
  current_events?: MapEvent[];
  upcoming_events?: MapEvent[];
  completed_count?: number;
  event_count?: number;
  conflicts?: Record<string, unknown>[];
  unscheduled_count?: number;
  required_equipment?: unknown[];
  assigned_staff?: { name: string; role: string | null }[];
  menu?: string[];
  dietary_coverage?: string[];
  hygiene_cert_expiry?: string | null;
  compliance_status?: string;
  compliance_verified?: boolean;
  verified_compliant?: boolean;
  hours?: string | null;
  opens?: string | null;
  closes?: string | null;
  is_open?: boolean | null;
  capacity_per_day?: number | null;
  availability?: string;
  rate?: number | null;
  payment_terms?: string | null;
  items?: MapItem[];
  item_count?: number;
  total_on_hand?: number;
  reserved_quantity?: number;
  under_repair_quantity?: number;
  recent_movements?: MapMovement[];
  event_requirements?: Record<string, unknown>[];
  allocations?: MapAllocation[];
  [key: string]: unknown;
};

export type MapLocation = {
  id: number;
  name: string;
  location_type: string;
  latitude: number | null;
  longitude: number | null;
  address: string | null;
  campus_zone: string | null;
  parent_location_id: number | null;
  source_reference: string | null;
  coordinate_verification_status: string;
  last_verified_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  mapped: boolean;
  coordinates_verified: boolean;
  links: MapLink[];
  layers: string[];
  contexts: Record<string, MapContext>;
  operational_status: MapStatus;
  has_incident: boolean;
  incident_count: number;
  potential_incident_count: number;
  incidents: MapIncident[];
  summary: Record<string, Record<string, unknown>>;
  layer_statuses: Record<string, MapStatus>;
  can_manage?: boolean;
  role?: string;
  duties?: MapDuty[];
  selected_at?: string;
  timezone?: string;
  date?: string;
};

export type MapDuty = {
  id: number;
  username: string;
  location_id: number;
  task_type: string;
  label: string | null;
  starts_at: string | null;
  ends_at: string | null;
  active: boolean;
  created_by: string | null;
};

export type MapSettings = {
  configured: boolean;
  center: { latitude: number; longitude: number };
  zoom: number;
  label: string | null;
  note: string | null;
  updated_at: string | null;
};

export type MapSummary = {
  mapped_locations: number;
  registry_locations: number;
  unmapped_total: number;
  unverified_coordinates: number;
  layers: Record<string, number>;
  status_counts: Record<string, number>;
  incidents: {
    active: number;
    potential: number;
    affected_locations: number;
    unlocated: number;
  };
  accommodation?: {
    hostel_blocks: number;
    external_properties: number;
    total_beds: number;
    allocated_beds: number;
    vacant_beds: number;
    occupancy_pct: number | null;
    active_plan: Record<string, unknown> | null;
  };
  events?: {
    venues: number;
    ongoing: number;
    upcoming: number;
    conflicts: number;
    unscheduled: number;
    available_venues: number;
  };
  logistics?: {
    stock_locations: number;
    items: number;
    under_repair: number;
    empty_locations: number;
  };
  vendors?: {
    total: number;
    serving: number;
    interrupted: number;
    compliance_failed: number;
    verified_compliant: number;
  };
  role: Role | string;
  generated_at: string;
  selected_at: string;
  timezone: string;
  date: string;
  can_manage_locations: boolean;
  poll_seconds: number;
  data_freshness?: {
    last_location_update: string | null;
    generated_at: string;
    source: string;
  };
};

export type MapEntity = {
  entity_type: string;
  entity_id: string;
  name: string;
  location_type: string;
  mapped: boolean;
  location_id: number | null;
  detail: Record<string, unknown>;
};

export type MapUnmappedItem = {
  kind: "registry" | "entity";
  location_id: number | null;
  entity_type?: string;
  entity_id?: string;
  name: string;
  location_type: string;
  reason: string;
  source_reference?: string | null;
  coordinate_verification_status?: string;
  detail?: Record<string, unknown>;
};

export type MapUnmapped = {
  total: number;
  unmapped: MapUnmappedItem[];
  unverified: MapUnmappedItem[];
  unverified_total: number;
};

export type MapLocationsResponse = {
  total: number;
  limit: number;
  offset: number;
  locations: MapLocation[];
  selected_at: string;
  timezone: string;
  date: string;
  poll_seconds: number;
};

export type MapIncidentsResponse = {
  incidents: MapIncident[];
  unlocated: MapIncident[];
  counts: { active: number; potential: number; unlocated: number };
  generated_at: string;
  note: string;
};

export type MapEntitiesResponse = {
  entities: MapEntity[];
  counts: { total: number; mapped: number; unmapped: number };
};

export type GeocodeResult = {
  display_name: string;
  latitude: number;
  longitude: number;
  category: string | null;
  type: string | null;
  address: Record<string, string>;
};

export type GeocodeResponse = {
  query: string;
  results: GeocodeResult[];
  attribution: string;
  note: string;
};

export const ROLE_LAYERS: Record<Role, string[]> = {
  director: [
    "hostel_block", "external_stay", "venue", "vendor",
    "inventory_location", "incident_location",
  ],
  accommodation_lead: ["hostel_block", "external_stay"],
  events_lead: ["venue"],
  logistics_lead: ["inventory_location"],
  vendor_lead: ["vendor"],
  volunteer: [],
  viewer: ["venue"],
};

export const LOCATION_TYPES = [
  "hostel_block", "external_stay", "venue", "vendor",
  "inventory_location", "incident_location",
];

export const TASK_TYPES = ["task", "pickup", "dropoff", "incident_report"];

export const TYPE_LABELS: Record<string, string> = {
  hostel_block: "Hostel block",
  external_stay: "External stay",
  venue: "Venue",
  vendor: "Food vendor",
  inventory_location: "Stock location",
  incident_location: "Incident point",
  incident: "Incident",
};

export function typeLabel(value: string): string {
  return TYPE_LABELS[value] ?? value.replaceAll("_", " ");
}

export function nowLocalInput(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}
