import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type Me } from "./api";
import { progress } from "./lib/progress";
import { Logo } from "./components/TopBar";

const Ctx = createContext<{ me: Me | null; signOut: () => Promise<void> }>({ me: null, signOut: async () => undefined });
export const useAuth = () => useContext(Ctx);

function LoginPage({ me, onDone }: { me: Me; onDone: () => void }) {
  const [mode, setMode] = useState<"login" | "signup">(me.signup ? "signup" : "login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await api.login(username, password);
      else await api.signup(username, password);
      progress.clearCache();
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand auth-brand"><span className="brand-mark"><Logo /></span>Signal Lab</div>
        <h1>{mode === "login" ? "Sign in" : "Create an account"}</h1>
        <label>
          <span>Username</span>
          <input className="input" autoComplete="username" autoFocus value={username} onChange={(e) => setUsername(e.target.value)} required />
        </label>
        <label>
          <span>Password</span>
          <input className="input" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "signup" ? 8 : undefined} value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <button className="btn btn-primary btn-lg" type="submit" disabled={busy}>{busy ? <span className="spinner" /> : null}{mode === "login" ? "Sign in" : "Create account"}</button>
        {me.signup && (
          <p className="auth-switch">
            {mode === "login" ? "No account? " : "Already have one? "}
            <button type="button" className="link-btn" onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(null); }}>
              {mode === "login" ? "Create one" : "Sign in"}
            </button>
          </p>
        )}
      </form>
    </main>
  );
}

/** Shows the sign-in page when the lab uses accounts and nobody is signed in. */
export function AuthGate({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api.me().then((m) => { setMe(m); setError(null); if (m.user) void progress.sync(); }, (e: Error) => setError(e.message)), []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const onUnauthorized = () => void load();
    window.addEventListener("sl:unauthorized", onUnauthorized);
    return () => window.removeEventListener("sl:unauthorized", onUnauthorized);
  }, [load]);
  const signOut = async () => {
    await api.logout();
    progress.clearCache();
    window.location.assign("/");
  };
  if (error) return <main className="auth-page"><p className="muted">Can't reach the lab: {error}</p></main>;
  if (!me) return null;
  if (me.auth === "accounts" && !me.user) return <LoginPage me={me} onDone={() => window.location.reload()} />;
  return <Ctx.Provider value={{ me, signOut }}>{children}</Ctx.Provider>;
}
