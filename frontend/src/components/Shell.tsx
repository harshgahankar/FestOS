import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useState } from "react";
import type { ReactNode } from "react";
import { useAuth } from "../auth";
import type { Role } from "../auth";
import { Badge } from "./ui";
import { Bunting } from "./Decor";
import { ChatbotLauncher } from "./chatbot/ChatbotLauncher";
import { ChatbotPanel } from "./chatbot/ChatbotPanel";

/**
 * Role-scoped nav. Mirrors backend require_role() so nobody is ever
 * shown a link that lands them on an unavoidable 403.
 * Module keys map to backend routers; routes point at placeholders for now.
 */
const NAV: { key: string; label: string; path: string; roles: Role[] }[] = [
  { key: "control", label: "Control Center", path: "/", roles: ["director"] },
  { key: "people", label: "People & Contingents", path: "/people", roles: ["director", "accommodation_lead", "events_lead", "logistics_lead", "viewer"] },
  { key: "accom", label: "Accommodation", path: "/accommodation", roles: ["director", "accommodation_lead"] },
  { key: "schedule", label: "Schedule", path: "/schedule", roles: ["director", "events_lead"] },
  { key: "inventory", label: "Inventory & Merch", path: "/inventory", roles: ["director", "logistics_lead", "volunteer"] },
  { key: "vendors", label: "Vendors", path: "/vendors", roles: ["director", "vendor_lead"] },
  { key: "disruptions", label: "Disruptions", path: "/disruptions", roles: ["director"] },
  { key: "audit", label: "Audit Log", path: "/audit", roles: ["director"] },
];

export default function Shell({ children }: { children?: ReactNode }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [isChatOpen, setIsChatOpen] = useState(false);
  const items = NAV.filter((n) => user && n.roles.includes(user.role));

  return (
    <div className="beige min-h-screen flex flex-col">
      <Bunting className="h-8 w-full shrink-0" />
      <div className="mx-auto flex flex-1 w-full max-w-7xl items-stretch gap-4 p-3 sm:p-5">
        <aside className="paper hidden w-56 shrink-0 rounded-sm border-2 border-crimson-dark/30 p-3 sm:flex sm:flex-col">
          <p className="font-display text-center text-xl text-ink">Aarohan 2026</p>
          <div className="my-2 border-t-2 border-teal-dark/20" />
          <nav className="flex flex-col gap-1">
            {items.map((n) => (
              <NavLink
                key={n.key}
                to={n.path}
                end={n.path === "/"}
                className={({ isActive }) =>
                  `rounded-sm px-2 py-1.5 text-sm font-bold text-ink/80 hover:bg-teal/20 transition ${
                    isActive ? "bg-mustard/80 text-ink" : ""
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="min-w-0 flex-1 flex flex-col">
          <header className="mb-4 flex items-center justify-between gap-3">
            <h1 className="wordmark text-2xl sm:text-3xl">
              <NavLink to="/" className="no-underline">
                FEST·OS
              </NavLink>
            </h1>
            <div className="flex items-center gap-2 sm:gap-3">
              {user && (
                <>
                  <span className="text-ink/80 text-sm font-bold sm:inline">{user.username}</span>
                  <Badge sev={user.role === "director" ? "warning" : "info"}>{user.role}</Badge>
                  <button
                    onClick={() => {
                      logout();
                      nav("/login", { replace: true });
                    }}
                    className="rounded-sm border-2 border-crimson-dark/50 px-2.5 py-1 text-xs font-bold uppercase tracking-wider text-crimson-deep hover:bg-crimson-dark/10 transition active:translate-y-px"
                  >
                    log out
                  </button>
                </>
              )}
            </div>
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

      <nav className="flex flex-wrap justify-center gap-1 border-t border-crimson-dark p-2 sm:hidden shrink-0">
        {items.map((n) => (
          <NavLink
            key={n.key}
            to={n.path}
            end={n.path === "/"}
            className={({ isActive }) =>
              `rounded-sm px-2 py-1 text-xs font-bold ${isActive ? "bg-mustard text-ink" : "text-ink/70"}`
            }
          >
            {n.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
