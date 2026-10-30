import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, setToken } from "./api";

export type Role =
  | "director"
  | "accommodation_lead"
  | "events_lead"
  | "logistics_lead"
  | "vendor_lead"
  | "volunteer"
  | "viewer";

export type Session = { username: string; role: Role };

type AuthState = {
  user: Session | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

const Ctx = createContext<AuthState | null>(null);

const KNOWN_ROLES: Role[] = [
  "director", "accommodation_lead", "events_lead", "logistics_lead",
  "vendor_lead", "volunteer", "viewer",
];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // token from a previous session: verify it still works via /auth/me
    if (!localStorage.getItem("festos_token")) {
      setLoading(false);
      return;
    }
    api<{ username: string; role: string }>("/auth/me")
      .then((me) => {
        const role = (KNOWN_ROLES as string[]).includes(me.role)
          ? (me.role as Role)
          : "viewer";
        setUser({ username: me.username, role });
      })
      .catch(() => setToken(""))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const out = await api<{ access_token: string; role: string }>("/auth/login", {
      method: "POST",
      body: { username, password },
    });
    setToken(out.access_token);
    const role = (KNOWN_ROLES as string[]).includes(out.role)
      ? (out.role as Role)
      : "viewer";
    setUser({ username, role });
  }, []);

  const logout = useCallback(() => {
    setToken("");
    setUser(null);
  }, []);

  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}
