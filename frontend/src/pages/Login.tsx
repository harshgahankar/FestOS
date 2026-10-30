import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { ApiError } from "../api";
import {
  scene, tear, flourishTop, flourishBottom,
  splashLeft, splashRight, sprigLeft, sprigRight,
} from "../posterArt";

interface DemoRole {
  role: string;
  badge: string;
  user: string;
  pass: string;
  description: string;
}

const DEMO_ROLES: DemoRole[] = [
  { role: "Director", badge: "All Access", user: "director", pass: "director123", description: "Full festival control & oversight" },
  { role: "Accm Lead", badge: "Hostels", user: "accommodation_lead", pass: "accom123", description: "Hostel allocations & room inventory" },
  { role: "Events", badge: "Stages", user: "events_lead", pass: "events123", description: "Schedules, clashes & stage production" },
  { role: "Logistics", badge: "Supply", user: "logistics_lead", pass: "logi123", description: "Equipment movement & merchandise" },
  { role: "Vendors", badge: "Food & Stalls", user: "vendor_lead", pass: "vendor123", description: "Catering compliance & settlements" },
  { role: "Volunteer", badge: "Ops Crew", user: "volunteer", pass: "vol123", description: "Check-in assistance & merch issue" },
  { role: "Viewer", badge: "Read Only", user: "viewer", pass: "view123", description: "Public schedule & general statistics" },
];

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [username, setUser] = useState("");
  const [password, setPass] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [selectedRole, setSelectedRole] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!username.trim()) {
      setError("Please enter a username or select a demo role.");
      return;
    }
    if (!password) {
      setError("Please enter your password.");
      return;
    }

    setBusy(true);
    try {
      await login(username.trim(), password);
      nav("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Network error — please check if the backend server is running.");
    } finally {
      setBusy(false);
    }
  }

  function handleSelectRole(d: DemoRole) {
    setUser(d.user);
    setPass(d.pass);
    setSelectedRole(d.user);
    setError("");
  }

  return (
    <div className="poster relative min-h-screen overflow-hidden bg-[#a53028]">
      {/* Background artwork */}
      <div className="scene-bg absolute inset-0 pointer-events-none select-none" dangerouslySetInnerHTML={{ __html: scene }} />
      <div className="tear-wrap absolute top-0 left-0 right-0 pointer-events-none select-none" dangerouslySetInnerHTML={{ __html: tear }} />
      <div className="art splash-l pointer-events-none select-none" dangerouslySetInnerHTML={{ __html: splashLeft }} />
      <div className="art splash-r pointer-events-none select-none" dangerouslySetInnerHTML={{ __html: splashRight }} />
      <div className="art sprig-l pointer-events-none select-none" dangerouslySetInnerHTML={{ __html: sprigLeft }} />
      <div className="art sprig-r pointer-events-none select-none" dangerouslySetInnerHTML={{ __html: sprigRight }} />

      <div className="relative z-10 flex min-h-screen flex-col">
        {/* Hero title & wordmark */}
        <div className="flex flex-1 flex-col items-center justify-center px-4 pt-4 sm:pt-6">
          <div className="art flourish-a select-none" dangerouslySetInnerHTML={{ __html: flourishTop }} />

          <h1 className="hero-word font-display my-2 select-none text-[15vw] leading-none sm:text-[7.5rem]">
            AAROहन
          </h1>

          <div className="art flourish-b select-none" dangerouslySetInnerHTML={{ __html: flourishBottom }} />

          {/* Enhanced Sign-in Card */}
          <div className="paper torn-b relative mt-5 w-full max-w-md rounded-sm border-2 border-crimson-dark/40 p-6 pb-8 shadow-[0_12px_24px_rgba(64,16,18,0.35),0_4px_0_#5c0f13] transition-all duration-300">
            {/* Card Header */}
            <div className="mb-4 text-center">
              <div className="inline-flex items-center gap-1.5 rounded-full border border-teal-dark/30 bg-teal/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-teal-dark mb-1.5">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-teal animate-pulse" />
                Operations Console
              </div>
              <h2 className="font-display text-2xl tracking-wide text-ink font-bold">
                Sign in to FestOS
              </h2>
              <p className="text-xs text-ink/70 font-sans mt-0.5">
                Aarohan 2026 Inter-College Festival Control
              </p>
            </div>

            <form onSubmit={submit} noValidate>
              {/* Username Input */}
              <div className="mb-3.5">
                <div className="flex items-center justify-between mb-1">
                  <label htmlFor="login-username" className="block text-xs font-bold uppercase tracking-wider text-ink/80">
                    Username / Role
                  </label>
                  {selectedRole && (
                    <span className="text-[10px] font-semibold text-teal-dark bg-teal/10 px-1.5 py-0.2 rounded-sm">
                      Role selected
                    </span>
                  )}
                </div>
                <div className="relative flex items-center">
                  <div className="pointer-events-none absolute left-3 flex items-center text-ink/50">
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  </div>
                  <input
                    id="login-username"
                    name="username"
                    type="text"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => { setUser(e.target.value); setSelectedRole(null); }}
                    placeholder="e.g. director, events_lead"
                    className="w-full rounded-sm border-2 border-teal-dark/40 bg-white/80 py-2 pl-9 pr-3 text-sm font-semibold text-ink placeholder:text-ink/35 outline-none transition focus:border-teal focus:bg-white focus:ring-2 focus:ring-teal/20"
                  />
                </div>
              </div>

              {/* Password Input */}
              <div className="mb-4">
                <div className="flex items-center justify-between mb-1">
                  <label htmlFor="login-password" className="block text-xs font-bold uppercase tracking-wider text-ink/80">
                    Password
                  </label>
                </div>
                <div className="relative flex items-center">
                  <div className="pointer-events-none absolute left-3 flex items-center text-ink/50">
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                  </div>
                  <input
                    id="login-password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => { setPass(e.target.value); setSelectedRole(null); }}
                    placeholder="Enter password"
                    className="w-full rounded-sm border-2 border-teal-dark/40 bg-white/80 py-2 pl-9 pr-10 text-sm font-semibold text-ink placeholder:text-ink/35 outline-none transition focus:border-teal focus:bg-white focus:ring-2 focus:ring-teal/20"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    title={showPassword ? "Hide password" : "Show password"}
                    className="absolute right-2.5 flex items-center rounded-sm p-1 text-ink/50 transition hover:bg-black/5 hover:text-ink focus:outline-none"
                  >
                    {showPassword ? (
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                      </svg>
                    ) : (
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {/* Error Alert */}
              {error && (
                <div className="mb-3.5 flex items-start gap-2 rounded-sm border-2 border-crimson bg-crimson-dark/95 p-2.5 text-xs text-cream shadow-md animate-in fade-in duration-200">
                  <svg className="h-4 w-4 shrink-0 text-mustard mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <span className="flex-1 font-medium leading-relaxed">{error}</span>
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={busy}
                className="group relative flex w-full items-center justify-center gap-2 rounded-sm border-2 border-teal-dark/60 bg-mustard px-4 py-2.5 text-sm font-bold uppercase tracking-[0.14em] text-crimson-deep shadow-[0_3px_0_#5c0f13] transition hover:bg-saffron hover:shadow-[0_4px_0_#5c0f13] active:translate-y-[2px] active:shadow-[0_1px_0_#5c0f13] disabled:opacity-60 disabled:pointer-events-none"
              >
                {busy ? (
                  <>
                    <svg className="h-4 w-4 animate-spin text-crimson-deep" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    <span>Authenticating…</span>
                  </>
                ) : (
                  <>
                    <span>Enter Portal</span>
                    <svg
                      className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:translate-y-0.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth="2.5"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                    </svg>
                  </>
                )}
              </button>
            </form>

            {/* Demo Roles Quick Fill Panel */}
            <div className="mt-5 border-t border-ink/15 pt-3.5">
              <div className="flex items-center justify-between mb-2">
                <span className="flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-ink/70">
                  <svg className="h-3.5 w-3.5 text-saffron" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Demo Roles
                </span>
                <span className="text-[10px] text-ink/50 font-medium">Click to populate</span>
              </div>

              <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
                {DEMO_ROLES.map((d) => {
                  const isSelected = selectedRole === d.user || (username === d.user && password === d.pass);
                  return (
                    <button
                      key={d.user}
                      type="button"
                      onClick={() => handleSelectRole(d)}
                      title={`${d.user} • ${d.description}`}
                      className={`flex flex-col items-start rounded-sm border px-2 py-1.5 text-left transition ${
                        isSelected
                          ? "border-teal-dark bg-teal-dark text-cream shadow-sm"
                          : "border-teal-dark/30 bg-teal/10 text-ink/80 hover:bg-teal/20 hover:border-teal-dark/50"
                      }`}
                    >
                      <span className="text-[11px] font-bold leading-tight">
                        {d.role}
                      </span>
                      <span className={`text-[9px] font-semibold leading-tight ${isSelected ? "text-cream/80" : "text-teal-dark"}`}>
                        {d.badge}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Bottom space buffer */}
        <div className="h-16 shrink-0 sm:h-20" />
      </div>
    </div>
  );
}
