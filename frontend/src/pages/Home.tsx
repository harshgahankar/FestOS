import { useAuth } from "../auth";
import { Paper } from "../components/ui";

const ROLE_MODULES: Record<string, string[]> = {
  accommodation_lead: ["People & Contingents", "Accommodation"],
  events_lead: ["People & Contingents", "Schedule"],
  logistics_lead: ["People & Contingents", "Inventory & Merch"],
  vendor_lead: ["Vendors"],
  volunteer: ["Inventory & Merch (issue desk)"],
  viewer: ["read-only views"],
};

/** Non-director landing: a friendly hub pointing at that role's modules. */
export default function Home() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <Paper title={`Welcome back, ${user.username}`}>
      <p className="mb-3 text-sm text-ink/80">
        You're signed in as <strong>{user.role}</strong>. Your work areas:
      </p>
      <ul className="mb-4 list-inside list-disc text-sm text-ink/80">
        {(ROLE_MODULES[user.role] ?? []).map((m) => <li key={m}>{m}</li>)}
      </ul>
      <p className="text-xs italic text-ink/60">
        Module screens are landing phase by phase. The director's Control Center aggregates
        every open finding from your work area — nothing resolves quietly, everything is audited.
      </p>
    </Paper>
  );
}
