import { useState } from "react";
import { api, type AdminUser } from "../api";
import { useLab } from "../context";
import { useAuth } from "../auth";
import { useAsync } from "../lib/hooks";
import TopBar from "../components/TopBar";

function ago(ts: number | null): string {
  if (!ts) return "never";
  const s = Date.now() / 1000 - ts;
  if (s < 90) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

export default function AdminPage() {
  const { lessons, findLesson, toast } = useLab();
  const { me } = useAuth();
  const users = useAsync(api.adminUsers, [], 15000);
  const [form, setForm] = useState({ username: "", password: "", role: "learner" });
  const [error, setError] = useState<string | null>(null);
  const total = lessons.length;

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.adminCreate(form.username, form.password, form.role);
      setForm({ username: "", password: "", role: "learner" });
      users.reload();
      toast(`Created ${form.username}`);
    } catch (err) { setError((err as Error).message); }
  };
  const act = async (fn: () => Promise<unknown>, msg: string) => {
    try { await fn(); users.reload(); toast(msg); } catch (err) { toast((err as Error).message); }
  };

  return (
    <div className="app">
      <TopBar crumbs={[{ label: "People" }]} />
      <main className="page">
        <div className="stack-page">
          <h1>People</h1>
          {me?.auth === "open" && <p className="muted">This lab runs in open mode: everyone shares the built-in account. Set <code>SIGNAL_LAB_AUTH=accounts</code> for per-person progress.</p>}
          <section className="section">
            <div className="table-wrap card">
              <table className="data-table">
                <thead><tr><th>Name</th><th>Role</th><th>Progress</th><th className="num">Runs</th><th>Last lesson</th><th>Active</th><th /></tr></thead>
                <tbody>
                  {(users.data ?? []).map((u: AdminUser) => (
                    <tr key={u.id}>
                      <td><b>{u.display_name}</b>{u.display_name !== u.username && <span className="subtle"> {u.username}</span>}</td>
                      <td>
                        <select className="select select-sm" value={u.role} disabled={u.id === me?.user?.id} onChange={(e) => act(() => api.adminPatch(u.id, { role: e.target.value }), `${u.username} is now ${e.target.value}`)}>
                          <option value="learner">learner</option>
                          <option value="admin">admin</option>
                        </select>
                      </td>
                      <td>
                        <div className="row" style={{ gap: 10 }}>
                          <div className="progress-bar" style={{ width: 80 }}>
                            <span className="done" style={{ width: `${(u.done / Math.max(1, total)) * 100}%` }} />
                            <span className="known" style={{ width: `${(u.known / Math.max(1, total)) * 100}%` }} />
                          </div>
                          <span className="subtle nowrap">{u.done} done{u.known ? ` · ${u.known} skipped` : ""}</span>
                        </div>
                      </td>
                      <td className="num">{u.runs}</td>
                      <td className="truncate">{u.last_lesson ? findLesson(u.last_lesson)?.title ?? u.last_lesson : "–"}</td>
                      <td className="nowrap subtle">{ago(u.last_seen)}</td>
                      <td className="actions">
                        {u.id !== me?.user?.id && me?.auth === "accounts" && (
                          <>
                            <button className="link-btn" onClick={() => { const pw = window.prompt(`New password for ${u.username} (8+ characters)`); if (pw) void act(() => api.adminPatch(u.id, { password: pw }), "Password changed"); }}>Reset password</button>
                            <button className="link-btn danger" onClick={() => { if (window.confirm(`Delete ${u.username} and their progress?`)) void act(() => api.adminDelete(u.id), `Deleted ${u.username}`); }}>Delete</button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {me?.auth === "accounts" && (
            <section className="section">
              <div className="section-head"><h2>Add a person</h2></div>
              <form className="inline-form" onSubmit={create}>
                <input className="input" placeholder="username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
                <input className="input" placeholder="password (8+)" type="password" minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
                <select className="select" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  <option value="learner">learner</option>
                  <option value="admin">admin</option>
                </select>
                <button className="btn btn-primary" type="submit">Add</button>
              </form>
              {error && <p className="auth-error">{error}</p>}
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
