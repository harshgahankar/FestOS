import { useEffect, useState, useMemo } from "react";
import { api } from "../api";
import type { TeamMember, TeamResponse } from "../teamTypes";
import { Spinner } from "../components/ui";

export default function Team() {
  const [data, setData] = useState<TeamResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  async function load() {
    setBusy(true);
    setErr("");
    try {
      const res = await api<TeamResponse>("/team");
      setData(res);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleRoleChange(member: TeamMember, newRole: string) {
    if (member.role === newRole) return;
    const oldRole = member.role;
    setUpdatingId(member.id);
    setNotice("");
    setErr("");

    // Optimistic update
    setData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        members: prev.members.map((m) =>
          m.id === member.id ? { ...m, role: newRole } : m
        ),
      };
    });

    try {
      await api<{ ok: boolean; member: TeamMember }>(`/team/${member.id}`, {
        method: "PATCH",
        body: { role: newRole, reason: `Role updated to ${newRole}` },
      });
      setNotice(`Updated ${member.name}'s role to "${newRole}" — logged to audit trail`);
    } catch (e) {
      // Revert on error
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          members: prev.members.map((m) =>
            m.id === member.id ? { ...m, role: oldRole } : m
          ),
        };
      });
      setErr(`Failed to update role: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setUpdatingId(null);
    }
  }

  async function handleShiftChange(member: TeamMember, newShift: string) {
    if (member.shift === newShift) return;
    const oldShift = member.shift;
    setUpdatingId(member.id);
    setNotice("");
    setErr("");

    // Optimistic update
    setData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        members: prev.members.map((m) =>
          m.id === member.id ? { ...m, shift: newShift } : m
        ),
      };
    });

    try {
      await api<{ ok: boolean; member: TeamMember }>(`/team/${member.id}`, {
        method: "PATCH",
        body: { shift: newShift, reason: `Shift updated to ${newShift}` },
      });
      setNotice(`Updated ${member.name}'s shift to "${newShift}" — logged to audit trail`);
    } catch (e) {
      // Revert on error
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          members: prev.members.map((m) =>
            m.id === member.id ? { ...m, shift: oldShift } : m
          ),
        };
      });
      setErr(`Failed to update shift: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setUpdatingId(null);
    }
  }

  const filteredMembers = useMemo(() => {
    if (!data?.members) return [];
    if (!search.trim()) return data.members;
    const q = search.toLowerCase().trim();
    return data.members.filter(
      (m) =>
        m.name.toLowerCase().includes(q) ||
        m.raw_id.toLowerCase().includes(q) ||
        m.role.toLowerCase().includes(q) ||
        m.shift.toLowerCase().includes(q)
    );
  }, [data?.members, search]);

  function renderMatrixBadge(val: string) {
    if (val === "edit") {
      return (
        <span className="inline-block px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase tracking-wider bg-teal/20 text-teal-dark border border-teal-dark/30">
          edit
        </span>
      );
    }
    if (val === "view") {
      return (
        <span className="inline-block px-2 py-0.5 rounded text-[11px] font-mono font-semibold lowercase tracking-wider bg-teal/10 text-teal-dark border border-teal-dark/20">
          view
        </span>
      );
    }
    if (val === "visible") {
      return (
        <span className="inline-block px-2 py-0.5 rounded text-[11px] font-mono font-bold lowercase tracking-wider bg-mustard/35 text-crimson-deep border border-mustard/60">
          visible
        </span>
      );
    }
    if (val === "masked") {
      return (
        <span className="inline-block px-2 py-0.5 rounded text-[11px] font-mono lowercase tracking-wider text-ink/40 bg-ink/5 border border-ink/10">
          masked
        </span>
      );
    }
    return <span className="text-ink/30 font-mono text-xs select-none">—</span>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="text-[11px] font-mono font-bold tracking-widest text-ink/50 uppercase mb-1">
          Team & Access
        </div>
        <h1 className="text-2xl lg:text-3xl font-extrabold text-crimson-deep tracking-tight">
          Roles, shifts and permissions
        </h1>
      </div>

      {/* Notifications */}
      {notice && (
        <p className="paper rounded-sm border-2 border-teal-dark/40 px-3.5 py-2 text-sm font-semibold text-teal-dark animate-in fade-in">
          {notice}
        </p>
      )}
      {err && (
        <p className="rounded-sm border border-saffron bg-crimson-dark/90 px-3.5 py-2 text-sm text-cream animate-in fade-in">
          {err}
        </p>
      )}
      {busy && !data && <Spinner label="loading team matrix & roster…" />}

      {data && (
        <>
          {/* Card 1: ACCESS MATRIX */}
          <div className="paper rounded-md border-2 border-crimson-dark/20 p-5 shadow-sm">
            <div className="text-[12px] font-mono font-bold tracking-wider text-ink/70 uppercase mb-3">
              ACCESS MATRIX
            </div>
            <div className="overflow-x-auto custom-scrollbar rounded-sm border border-crimson-dark/15 bg-white/40">
              <table className="w-full text-left border-collapse min-w-[840px]">
                <thead className="bg-crimson-dark/10 text-[11px] font-mono uppercase tracking-wider text-ink/75">
                  <tr>
                    <th className="px-4 py-2.5 font-bold">ROLE</th>
                    <th className="px-3 py-2.5 font-bold">PARTICIPANTS</th>
                    <th className="px-3 py-2.5 font-bold">ACCOMMODATION</th>
                    <th className="px-3 py-2.5 font-bold">EVENTS</th>
                    <th className="px-3 py-2.5 font-bold">LOGISTICS</th>
                    <th className="px-3 py-2.5 font-bold">VENDORS</th>
                    <th className="px-3 py-2.5 font-bold">TEAM</th>
                    <th className="px-3 py-2.5 font-bold">AUDIT</th>
                    <th className="px-3 py-2.5 font-bold">CONTACT</th>
                    <th className="px-3 py-2.5 font-bold">MEDICAL</th>
                    <th className="px-3 py-2.5 font-bold">ACCESS./ROOM</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink/10 text-xs">
                  {data.access_matrix.map((row) => (
                    <tr
                      key={row.role}
                      className="hover:bg-mustard/10 transition-colors align-middle"
                    >
                      <td className="px-4 py-3 font-mono font-bold text-ink">
                        {row.role}
                      </td>
                      <td className="px-3 py-3">{renderMatrixBadge(row.participants)}</td>
                      <td className="px-3 py-3">{renderMatrixBadge(row.accommodation)}</td>
                      <td className="px-3 py-3">{renderMatrixBadge(row.events)}</td>
                      <td className="px-3 py-3">{renderMatrixBadge(row.logistics)}</td>
                      <td className="px-3 py-3">{renderMatrixBadge(row.vendors)}</td>
                      <td className="px-3 py-3">{renderMatrixBadge(row.team)}</td>
                      <td className="px-3 py-3">{renderMatrixBadge(row.audit)}</td>
                      <td className="px-3 py-3">{renderMatrixBadge(row.contact)}</td>
                      <td className="px-3 py-3">{renderMatrixBadge(row.medical)}</td>
                      <td className="px-3 py-3">{renderMatrixBadge(row.access_room)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Card 2: CORE TEAM */}
          <div className="paper rounded-md border-2 border-crimson-dark/20 p-5 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
              <div className="text-[12px] font-mono font-bold tracking-wider text-ink/70 uppercase">
                CORE TEAM ({data.count})
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="filter core team…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="rounded border border-crimson-dark/20 bg-white/70 px-2.5 py-1 text-xs text-ink placeholder:text-ink/40 focus:border-crimson-dark focus:outline-none focus:ring-1 focus:ring-crimson-dark"
                />
              </div>
            </div>

            <div className="overflow-x-auto max-h-[560px] overflow-y-auto custom-scrollbar rounded-sm border border-crimson-dark/15 bg-white/40">
              <table className="w-full text-left border-collapse min-w-[500px]">
                <thead className="sticky top-0 z-10 bg-crimson-dark/15 backdrop-blur-sm text-[11px] font-mono uppercase tracking-wider text-ink/75 border-b border-crimson-dark/15">
                  <tr>
                    <th className="px-4 py-2.5 font-bold w-20">ID</th>
                    <th className="px-4 py-2.5 font-bold">NAME</th>
                    <th className="px-4 py-2.5 font-bold w-48">ROLE</th>
                    <th className="px-4 py-2.5 font-bold w-44">SHIFT</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink/10 text-xs">
                  {filteredMembers.map((m) => {
                    const isUpdating = updatingId === m.id;
                    const isDirector = m.role === "director";

                    return (
                      <tr
                        key={m.id}
                        className="hover:bg-mustard/10 transition-colors align-middle"
                      >
                        <td className="px-4 py-3 font-mono font-bold text-ink/80">
                          {m.raw_id}
                        </td>
                        <td className="px-4 py-3 font-medium text-ink">
                          {m.name}
                        </td>
                        <td className="px-4 py-3">
                          {isDirector ? (
                            <span className="font-mono text-xs font-semibold text-ink px-2.5 py-1 inline-block">
                              director
                            </span>
                          ) : (
                            <div className="relative inline-block w-full max-w-[170px]">
                              <select
                                value={m.role}
                                disabled={isUpdating}
                                onChange={(e) => void handleRoleChange(m, e.target.value)}
                                className="w-full appearance-none rounded border border-crimson-dark/25 bg-cream/80 py-1 pl-2.5 pr-7 text-xs font-mono font-medium text-ink hover:border-crimson-dark focus:border-crimson-dark focus:outline-none focus:ring-1 focus:ring-crimson-dark transition disabled:opacity-50 cursor-pointer shadow-2xs"
                              >
                                {data.roles.map((r) => (
                                  <option key={r} value={r}>
                                    {r}
                                  </option>
                                ))}
                              </select>
                              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-ink/60 text-[10px]">
                                ▾
                              </div>
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <div className="relative inline-block w-full max-w-[150px]">
                            <select
                              value={m.shift}
                              disabled={isUpdating}
                              onChange={(e) => void handleShiftChange(m, e.target.value)}
                              className="w-full appearance-none rounded border border-crimson-dark/25 bg-cream/80 py-1 pl-2.5 pr-7 text-xs font-mono font-medium text-ink hover:border-crimson-dark focus:border-crimson-dark focus:outline-none focus:ring-1 focus:ring-crimson-dark transition disabled:opacity-50 cursor-pointer shadow-2xs"
                            >
                              {data.shifts.map((s) => (
                                <option key={s} value={s}>
                                  {s}
                                </option>
                              ))}
                            </select>
                            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-ink/60 text-[10px]">
                              ▾
                            </div>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-[11px] italic text-ink/60">
              Role and shift reassignments take effect immediately and are logged directly to the immutable audit ledger.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
