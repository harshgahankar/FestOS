import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useState } from "react";
import type { ReactNode } from "react";
import { useAuth } from "../auth";
import type { Role } from "../auth";
import { Bunting } from "./Decor";
import { ChatbotLauncher } from "./chatbot/ChatbotLauncher";
import { ChatbotPanel } from "./chatbot/ChatbotPanel";

type NavItem = {
  key: string;
  label: string;
  path: string;
  roles: Role[];
  badge?: number | string;
  icon: ReactNode;
};

/**
 * Role-scoped nav with custom icons matching the exact design specification.
 * Mirrors backend require_role() so nobody is ever shown a link that lands them on an unavoidable 403.
 */
const NAV: NavItem[] = [
  {
    key: "control",
    label: "Command Center",
    path: "/",
    roles: ["director"],
    badge: 5,
    icon: (
      <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
      </svg>
    ),
  },
  {
    key: "people",
    label: "Participants",
    path: "/people",
    roles: ["director", "accommodation_lead", "events_lead", "logistics_lead", "viewer"],
    icon: (
      <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
  {
    key: "accom",
    label: "Accommodation",
    path: "/accommodation",
    roles: ["director", "accommodation_lead"],
    icon: (
      <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 4v16M2 8h18a2 2 0 0 1 2 2v10M2 17h20M6 8v9" />
      </svg>
    ),
  },
  {
    key: "schedule",
    label: "Events & Venues",
    path: "/schedule",
    roles: ["director", "events_lead"],
    icon: (
      <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 7.5V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3.5" />
        <path d="M16 2v4M8 2v4M3 10h18" />
        <circle cx="16" cy="16" r="5" />
        <path d="M16 14v2l1.5 1" />
      </svg>
    ),
  },
  {
    key: "inventory",
    label: "Logistics & Merch",
    path: "/inventory",
    roles: ["director", "logistics_lead", "volunteer"],
    icon: (
      <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
        <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
        <line x1="12" y1="22.08" x2="12" y2="12" />
      </svg>
    ),
  },
  {
    key: "vendors",
    label: "Food Vendors",
    path: "/vendors",
    roles: ["director", "vendor_lead"],
    icon: (
      <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 2v20M18 2a3 3 0 0 1 3 3v4a3 3 0 0 1-3 3M6 2v20M3 2v6a3 3 0 0 0 6 0V2" />
      </svg>
    ),
  },
  {
    key: "team",
    label: "Team & Access",
    path: "/team",
    roles: ["director"],
    icon: (
      <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        <path d="m9 12 2 2 4-4" />
      </svg>
    ),
  },
  {
    key: "audit",
    label: "Audit & Decisions",
    path: "/audit",
    roles: ["director"],
    icon: (
      <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 2h8a2 2 0 0 1 2 2v14a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V6a4 4 0 0 1 4-4z" />
        <path d="M8 7h8M8 11h8M8 15h4" />
      </svg>
    ),
  },
];

const FEST_START = new Date("2026-10-30T00:00:00");
const FEST_DAYS = 3;
const FEST_END = new Date(FEST_START.getTime() + FEST_DAYS * 24 * 60 * 60 * 1000);

function festDay(): { label: string; progress: number } {
  const now = new Date();
  if (now < FEST_START) {
    const days = Math.ceil((FEST_START.getTime() - now.getTime()) / 86400000);
    return { label: days > 1 ? `starts in ${days} days` : "starts tomorrow", progress: 0 };
  }
  if (now >= FEST_END) return { label: "wrapped up", progress: 100 };
  const day = Math.floor((now.getTime() - FEST_START.getTime()) / 86400000) + 1;
  return { label: `day ${day} of ${FEST_DAYS}`, progress: ((day - 1) / FEST_DAYS) * 100 + 100 / FEST_DAYS };
}

function formatRoleName(role?: Role | string): string {
  if (!role) return "User";
  switch (role) {
    case "director":
      return "Festival Director";
    case "accommodation_lead":
      return "Accommodation Lead";
    case "events_lead":
      return "Events Lead";
    case "logistics_lead":
      return "Logistics Lead";
    case "vendor_lead":
      return "Vendor Lead";
    case "volunteer":
      return "Volunteer Staff";
    case "viewer":
      return "Guest Viewer";
    default:
      return role.charAt(0).toUpperCase() + role.slice(1);
  }
}

export default function Shell({ children }: { children?: ReactNode }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [isChatOpen, setIsChatOpen] = useState(false);
  const items = NAV.filter((n) => user && n.roles.includes(user.role));
  const day = festDay();

  const groups: { label: string; sub: NavItem[] }[] = [
    {
      label: "Operate",
      sub: items.filter((n) =>
        ["control", "people", "accom", "schedule", "inventory", "vendors"].includes(n.key)
      ),
    },
    { label: "Govern", sub: items.filter((n) => ["team", "audit"].includes(n.key)) },
  ].filter((g) => g.sub.length > 0);

  return (
    <div className="beige min-h-screen flex flex-col">
      <Bunting className="h-8 w-full shrink-0" />
      <div className="flex flex-1 w-full items-stretch gap-4 p-3 sm:p-5 sm:pl-4">
        {/* Sidebar at the left edge of the layout, full height */}
        <aside className="paper relative hidden w-72 shrink-0 flex-col rounded-md border-2 border-crimson-dark/30 shadow-[0_3px_0_rgba(64,16,18,0.35)] sm:flex select-none">
          <div className="flex min-h-0 flex-1 flex-col p-4">
            {/* Header: FESTOS / Aarohan 2026 */}
            <div className="mb-4 px-1 pt-1">
              <p className="text-[11px] font-mono font-bold uppercase tracking-wider text-saffron">
                FESTOS
              </p>
              <h2 className="font-display text-2xl font-bold tracking-tight text-ink mt-0.5">
                Aarohan 2026
              </h2>
              <div className="my-2.5 border-t-2 border-teal-dark/20" />
            </div>

            {/* Nav items, grouped by concern */}
            <nav className="flex flex-col space-y-4 overflow-y-auto">
              {groups.map((g) => (
                <div key={g.label} className="flex flex-col space-y-1">
                  <p className="px-3 text-[10px] font-mono font-bold uppercase tracking-[0.18em] text-crimson-dark/60">
                    {g.label}
                  </p>
                  {g.sub.map((n) => (
                    <NavLink
                      key={n.key}
                      to={n.path}
                      end={n.path === "/"}
                      className={({ isActive }) =>
                        `group flex items-center gap-3 px-3 py-2 rounded-sm text-sm transition-all ${
                          isActive
                            ? "bg-mustard text-ink font-bold shadow-xs border-2 border-mustard-dark/40 ring-1 ring-mustard/30"
                            : "text-ink/80 hover:text-ink hover:bg-teal/20 font-semibold"
                        }`
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <span className={`shrink-0 transition-colors ${isActive ? "text-ink" : "text-ink/65 group-hover:text-crimson-deep"}`}>
                            {n.icon}
                          </span>
                          <span className="truncate">{n.label}</span>
                          {n.badge !== undefined && (
                            <span className="ml-auto rounded-sm bg-crimson-dark text-cream border border-saffron/40 px-1.5 py-0.5 text-[10px] font-bold shadow-xs leading-none">
                              {n.badge}
                            </span>
                          )}
                        </>
                      )}
                    </NavLink>
                  ))}
                </div>
              ))}
            </nav>

            {/* Festival status card fills the gap below nav */}
            <div className="mt-auto pt-5 px-1">
              <div className="rounded-sm border-2 border-teal-dark/25 bg-teal/10 p-2.5">
                <div className="flex items-center justify-between">
                  <span className="rounded-sm bg-teal/25 px-1.5 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider text-teal-dark">
                    live
                  </span>
                  <span className="h-1.5 w-1.5 rounded-full bg-teal animate-pulse" />
                </div>
                <p className="mt-1.5 font-display text-xl font-extrabold leading-none text-ink">
                  {day.label}
                </p>
                <p className="mt-1 text-[11px] text-ink/60">
                  Oct 30 – Nov 1 · 10 venues
                </p>
                <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-ink/10">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-saffron to-crimson"
                    style={{ width: `${day.progress}%` }}
                  />
                </div>
                <div className="mt-2 flex justify-between">
                  {[1, 2, 3].map((d) => (
                    <span
                      key={d}
                      className={`rounded-sm border px-1.5 text-[10px] font-mono font-bold ${
                        day.progress >= (d / FEST_DAYS) * 100 - 100 / FEST_DAYS / 2
                          ? "border-teal-dark/40 bg-teal/20 text-teal-dark"
                          : "border-ink/15 text-ink/45"
                      }`}
                    >
                      day {d}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* User profile & sign out footer */}

          {/* User profile & sign out footer */}
          {user && (
            <div className="border-t-2 border-crimson-dark/20 pt-3.5 mt-5 px-1">
              <p className="text-sm font-bold text-ink leading-tight">
                {formatRoleName(user.role)}
              </p>
              <p className="font-mono text-xs text-ink/60 mt-0.5">
                {user.username}
              </p>
              <button
                onClick={() => {
                  logout();
                  nav("/login", { replace: true });
                }}
                className="mt-3 inline-flex items-center gap-1.5 rounded-sm border-2 border-crimson-dark/50 bg-white/60 px-2.5 py-1 text-xs font-bold uppercase tracking-wider text-crimson-deep hover:bg-crimson-dark/10 transition active:translate-y-px cursor-pointer"
              >
                <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                <span>Sign out</span>
              </button>
            </div>
          )}
        </aside>

        <main className="min-w-0 flex-1 flex flex-col">
          <header className="mb-4 flex items-center justify-between gap-3">
            <NavLink
              to="/"
              className="group inline-flex items-center gap-2.5 no-underline transition hover:opacity-90"
              title="FestOS — Festival Operations System"
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-crimson to-crimson-dark border-2 border-crimson-deep shadow-xs text-mustard transition-transform duration-200 group-hover:scale-105">
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2L14.5 8.5L21.5 9.5L16.5 14.5L17.5 21.5L12 18L6.5 21.5L7.5 14.5L2.5 9.5L9.5 8.5L12 2Z" />
                </svg>
              </span>
              <span className="flex items-baseline">
                <span className="font-display text-2xl sm:text-3xl font-extrabold tracking-tight text-crimson-deep">
                  FEST
                </span>
                <span className="mx-0.5 font-sans text-2xl font-black text-saffron">
                  ·
                </span>
                <span className="font-display text-2xl sm:text-3xl font-extrabold tracking-tight text-mustard">
                  OS
                </span>
                <span className="ml-2 hidden rounded-md border border-crimson-dark/20 bg-white/70 px-1.5 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider text-teal-dark md:inline-block shadow-xs">
                  v1.0
                </span>
              </span>
            </NavLink>
          </header>
          {children ?? <Outlet />}
        </main>
      </div>

      {/* Floating launcher for convenient access across pages */}
      {user && !isChatOpen && (
        <div className="fixed bottom-6 right-6 z-40">
          <ChatbotLauncher
            onClick={() => setIsChatOpen(true)}
            isOpen={isChatOpen}
          />
        </div>
      )}

      {/* FestOS AI Operations Panel */}
      {user && (
        <ChatbotPanel
          isOpen={isChatOpen}
          onClose={() => setIsChatOpen(false)}
          userRole={user.role}
        />
      )}

      {/* Mobile nav bar */}
      <nav className="paper flex flex-wrap justify-center gap-1 border-t-2 border-crimson-dark/30 p-2 sm:hidden shrink-0">
        {items.map((n) => (
          <NavLink
            key={n.key}
            to={n.path}
            end={n.path === "/"}
            className={({ isActive }) =>
              `rounded-sm px-2 py-1 text-xs font-bold flex items-center gap-1 transition ${
                isActive ? "bg-mustard text-ink" : "text-ink/80 hover:bg-teal/20"
              }`
            }
          >
            <span>{n.label}</span>
          </NavLink>
        ))}
        {user && (
          <button
            onClick={() => {
              logout();
              nav("/login", { replace: true });
            }}
            className="rounded-sm px-2 py-1 text-xs font-bold text-crimson-deep hover:bg-crimson-dark/10 transition"
          >
            Sign out
          </button>
        )}
      </nav>
    </div>
  );
}
