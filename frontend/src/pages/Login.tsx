import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { ApiError } from "../api";
import {
  scene, tear, flourishTop, flourishBottom,
  splashLeft, splashRight, sprigLeft, sprigRight,
} from "../posterArt";

const DEMO: { role: string; user: string; pass: string }[] = [
  { role: "director", user: "director", pass: "director123" },
  { role: "accm lead", user: "accommodation_lead", pass: "accom123" },
  { role: "events", user: "events_lead", pass: "events123" },
  { role: "logistics", user: "logistics_lead", pass: "logi123" },
  { role: "vendors", user: "vendor_lead", pass: "vendor123" },
  { role: "volunteer", user: "volunteer", pass: "vol123" },
  { role: "viewer", user: "viewer", pass: "view123" },
];

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [username, setUser] = useState("");
  const [password, setPass] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(username.trim(), password);
      nav("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "network error — is the backend running?");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="poster relative min-h-screen overflow-hidden bg-[#a53028]">
      {/* exact artwork backdrop */}
      <div className="scene-bg absolute inset-0" dangerouslySetInnerHTML={{ __html: scene }} />
      <div className="tear-wrap absolute top-0 left-0 right-0" dangerouslySetInnerHTML={{ __html: tear }} />
      <div className="art splash-l" dangerouslySetInnerHTML={{ __html: splashLeft }} />
      <div className="art splash-r" dangerouslySetInnerHTML={{ __html: splashRight }} />
      <div className="art sprig-l" dangerouslySetInnerHTML={{ __html: sprigLeft }} />
      <div className="art sprig-r" dangerouslySetInnerHTML={{ __html: sprigRight }} />

      <div className="relative z-10 flex min-h-screen flex-col">
        {/* hero: wordmark between flourishes */}
        <div className="flex flex-1 flex-col items-center justify-center px-4 pt-6">
          <div className="art flourish-a" dangerouslySetInnerHTML={{ __html: flourishTop }} />

          <h1 className="hero-word font-display my-3 select-none text-[16vw] leading-none sm:text-[8.5rem]">
            AAROहन
          </h1>

          <div className="art flourish-b" dangerouslySetInnerHTML={{ __html: flourishBottom }} />

          {/* the sign-in card lives where REGISTER sat */}
          <form
            onSubmit={submit}
            className="paper torn-b relative mt-6 w-full max-w-sm rounded-sm border-2 border-crimson-dark/40 p-5 pb-6 shadow-[0_8px_0_rgba(64,16,18,0.45)]"
          >
            <h2 className="font-display mb-3 text-center text-xl text-ink">Sign in</h2>

            <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-ink/70">
              Username / role
            </label>
            <input
              value={username}
              onChange={(e) => setUser(e.target.value)}
              className="mb-3 w-full rounded-sm border-2 border-teal-dark/50 bg-white/60 px-3 py-1.5 text-ink outline-none focus:border-teal"
            />

            <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-ink/70">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPass(e.target.value)}
              className="mb-3 w-full rounded-sm border-2 border-teal-dark/50 bg-white/60 px-3 py-1.5 text-ink outline-none focus:border-teal"
            />

            {error && (
              <p className="mb-3 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-1.5 text-sm text-cream">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="mx-auto flex w-full items-center justify-center gap-2 rounded-sm bg-mustard px-4 py-2.5 text-base font-bold uppercase tracking-[0.14em] text-crimson-deep transition hover:bg-saffron disabled:opacity-60"
            >
              {busy ? "checking…" : <>ENTER ↓</>}
            </button>

            <div className="mt-4 border-t border-ink/20 pt-2.5">
              <p className="mb-1.5 text-center text-[10px] font-bold uppercase tracking-wider text-ink/50">
                demo roles — click to fill
              </p>
              <div className="flex flex-wrap justify-center gap-1">
                {DEMO.map((d) => (
                  <button
                    key={d.user}
                    type="button"
                    onClick={() => { setUser(d.user); setPass(d.pass); }}
                    className="rounded-sm border border-teal-dark/40 bg-teal/15 px-1.5 py-0.5 text-[10px] font-semibold text-teal-dark hover:bg-teal/30"
                  >
                    {d.role}
                  </button>
                ))}
              </div>
            </div>
          </form>
        </div>

        <div className="h-24 shrink-0 sm:h-28" />
      </div>
    </div>
  );
}
