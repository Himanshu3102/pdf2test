import { useEffect, useRef, useState, useMemo } from "react";
import type { FormEvent } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import { api, clearToken, getToken, setToken, uploadPdf } from "./api";
import type { AuthUser, ExamHistory } from "./api";

type Exam = any;
type Screen = "boot" | "auth" | "home" | "upload" | "review" | "runner" | "results" | "gate_papers";

function MathText({ text }: { text: string }) {
  const html = useMemo(() => {
    const parts = text.split(/(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g);
    let out = "";
    for (const part of parts) {
      if (part.startsWith("$$") && part.endsWith("$$") && part.length > 4) {
        out += katex.renderToString(part.slice(2, -2), { displayMode: true, throwOnError: false });
      } else if (part.startsWith("$") && part.endsWith("$") && part.length > 2) {
        out += katex.renderToString(part.slice(1, -1), { displayMode: false, throwOnError: false });
      } else {
        out += part
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/\n/g, "<br/>");
      }
    }
    return out;
  }, [text]);
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}

function formatMark(value?: number | null): string {
  if (value == null || value === 0) return "0";
  const abs = Math.abs(value);
  if (Math.abs(abs - 1 / 3) < 0.02) return "1/3";
  if (Math.abs(abs - 2 / 3) < 0.02) return "2/3";
  return abs.toFixed(2).replace(/\.?0+$/, "");
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function attemptLabel(status: string): string {
  if (status === "in_progress") return "In progress";
  if (status === "expired") return "Time expired";
  return "Submitted";
}

export default function App() {
  const resumeAttemptId = new URLSearchParams(window.location.search).get("attempt");
  const [screen, setScreen] = useState<Screen>("boot");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [history, setHistory] = useState<ExamHistory[]>([]);
  const [exam, setExam] = useState<Exam | null>(null);
  const [attemptId, setAttemptId] = useState<string | null>(resumeAttemptId);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [parseWarnings, setParseWarnings] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);

  async function openAttempt(id: string) {
    setAttemptId(id);
    setError(null);
    try {
      const attempt = await api(`/attempts/${id}`);
      if (attempt.status && attempt.status !== "in_progress") {
        const r = await api(`/attempts/${id}/results`);
        setResults(r);
        setScreen("results");
      } else {
        setScreen("runner");
      }
    } catch (e: any) {
      setError(e?.message || "Could not open that attempt.");
      setScreen("home");
    }
  }

  // Restore the session from the stored token on first load.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!getToken()) {
        setScreen("auth");
        return;
      }
      try {
        const me = await api("/auth/me");
        if (cancelled) return;
        setUser(me);
        if (resumeAttemptId) {
          await openAttempt(resumeAttemptId);
        } else {
          setScreen("home");
        }
      } catch {
        if (cancelled) return;
        clearToken();
        setUser(null);
        setScreen("auth");
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A 401 from any request drops the session and returns to login.
  useEffect(() => {
    function onLogout() {
      setUser(null);
      setHistory([]);
      setExam(null);
      setResults(null);
      setScreen("auth");
    }
    window.addEventListener("exam:logout", onLogout);
    return () => window.removeEventListener("exam:logout", onLogout);
  }, []);

  // Refresh the dashboard whenever it becomes visible.
  useEffect(() => {
    if (screen !== "home" || !user) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await api("/me/exams");
        if (!cancelled) setHistory(data);
      } catch (e: any) {
        if (!cancelled) setError(e?.message || "Could not load your tests.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [screen, user]);

  function handleAuthed(u: AuthUser) {
    setUser(u);
    setError(null);
    setScreen("home");
  }

  async function handleLogout() {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      // stateless token; ignoring the server call is fine
    }
    clearToken();
    setUser(null);
    setHistory([]);
    setExam(null);
    setResults(null);
    setAttemptId(null);
    setScreen("auth");
  }

  async function handleUpload(file: File) {
    setUploading(true);
    try {
      setError(null);
      setParseWarnings([]);
      const data = await uploadPdf(file);
      let exam = data.exam;
      // Poll while the backend processes (OCR/vision) in the background.
      while (exam.status === "processing") {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const refreshed = await api(`/exams/${exam.id}`);
        exam = refreshed;
      }
      if (exam.status === "failed") {
        setError(exam.instructions || "Processing failed.");
        return;
      }
      setExam(exam);
      setParseWarnings(data.warnings || []);
      setScreen("review");
    } catch (e: any) {
      setError(e?.message || "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function refreshExam(id: string) {
    const updated = await api(`/exams/${id}`);
    setExam(updated);
  }

  async function handlePublish(overrides?: { title: string; settings: any; settingsConfirmed: boolean }) {
    if (!exam) return;
    try {
      setError(null);
      if (overrides) {
        const updated = await api(`/exams/${exam.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            title: overrides.title,
            settings: overrides.settings,
            settings_confirmed: overrides.settingsConfirmed,
            questions: exam.questions,
          }),
        });
        setExam(updated);
      }
      await api(`/exams/${exam.id}/publish`, { method: "POST" });
      await refreshExam(exam.id);
      const att = await api(`/exams/${exam.id}/attempts`, { method: "POST" });
      setAttemptId(att.attempt_id);
      setScreen("runner");
    } catch (e: any) {
      setError(e?.message || "Could not start the test.");
    }
  }

  async function handleStart(examId: string) {
    try {
      setError(null);
      const att = await api(`/exams/${examId}/attempts`, { method: "POST" });
      setAttemptId(att.attempt_id);
      setScreen("runner");
    } catch (e: any) {
      setError(e?.message || "Could not start the test.");
    }
  }

  async function handleContinueDraft(examId: string) {
    try {
      setError(null);
      const data = await api(`/exams/${examId}`);
      setExam(data);
      setScreen("review");
    } catch (e: any) {
      setError(e?.message || "Could not open that test.");
    }
  }

  async function handleViewResult(id: string) {
    try {
      setError(null);
      const r = await api(`/attempts/${id}/results`);
      setResults(r);
      setScreen("results");
    } catch (e: any) {
      setError(e?.message || "Could not load that result.");
    }
  }

  function handleResults(r: any) {
    setResults(r);
    setScreen("results");
  }

  function goHome() {
    setResults(null);
    setExam(null);
    setScreen("home");
  }

  return (
    <div className={screen === "runner" ? "app app--runner" : screen === "auth" ? "app app--auth" : "app"}>
      {screen !== "runner" && screen !== "boot" && screen !== "auth" && (
        <header className="site-header">
          <div className="site-brand">
            <span className="site-brand-mark">pdf2test</span>
          </div>
          {user && (
            <div className="site-user">
              <span className="user-chip" title={user.username}>
                {user.username}
              </span>
              <button className="ghost" onClick={handleLogout}>
                Log out
              </button>
            </div>
          )}
        </header>
      )}

      {error && (
        <div className="error">
          <span>{error}</span>
          <button className="ghost error-dismiss" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {screen === "boot" && <div className="loading">Loading…</div>}

      {screen === "auth" && !user && <AuthScreen onAuthed={handleAuthed} />}

      {screen === "home" && user && (
        <HomeScreen
          user={user}
          exams={history}
          onNewUpload={() => setScreen("upload")}
          onGatePapers={() => setScreen("gate_papers")}
          onContinueDraft={handleContinueDraft}
          onStart={handleStart}
          onResume={openAttempt}
          onViewResult={handleViewResult}
        />
      )}

      {screen === "gate_papers" && <GatePapersScreen onBack={goHome} onStartExam={handleStart} />}
      {screen === "upload" && <UploadScreen onUpload={handleUpload} onBack={goHome} uploading={uploading} />}

      {screen === "review" && exam && (
        <ReviewScreen exam={exam} setExam={setExam} onPublish={handlePublish} onBack={goHome} warnings={parseWarnings} />
      )}

      {screen === "runner" && attemptId && (
        <RunnerScreen
          attemptId={attemptId}
          username={user?.username || "Candidate"}
          onFinish={handleResults}
          onExit={goHome}
        />
      )}

      {screen === "results" && results && <ResultsScreen results={results} onBack={goHome} />}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Authentication                                                      */
/* ------------------------------------------------------------------ */

function AuthScreen({ onAuthed }: { onAuthed: (user: AuthUser) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function switchMode(next: "login" | "register") {
    setMode(next);
    setError(null);
    setPassword("");
    setConfirm("");
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const u = username.trim();
    if (mode === "register") {
      if (u.length < 3) {
        setError("Username must be at least 3 characters.");
        return;
      }
      if (password.length < 8) {
        setError("Password must be at least 8 characters.");
        return;
      }
      if (password !== confirm) {
        setError("Passwords do not match.");
        return;
      }
    }
    setBusy(true);
    try {
      const res = await api(`/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify({ username: username.trim(), password }),
      });
      setToken(res.access_token);
      onAuthed(res.user);
    } catch (err: any) {
      setError(err?.message || "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <section className="auth-hero">
        <div className="auth-logo">pdf2test</div>
        <h1>pdf2test</h1>
        <p>
          Turn a PDF question paper into a realistic mock test, then review your score, per-question
          timing, and every attempt you have taken.
        </p>
        <ul className="auth-points">
          <li>Upload a paper once and keep it in your library</li>
          <li>Server-backed timer with autosave and resume</li>
          <li>Saved results and progress for your account</li>
        </ul>
      </section>

      <section className="auth-card">
        <div className="auth-tabs" role="tablist">
          <button
            type="button"
            className={mode === "login" ? "active" : ""}
            onClick={() => switchMode("login")}
          >
            Log in
          </button>
          <button
            type="button"
            className={mode === "register" ? "active" : ""}
            onClick={() => switchMode("register")}
          >
            Register
          </button>
        </div>

        <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
        <p className="muted">
          {mode === "login"
            ? "Log in to continue your practice."
            : "Register once. Your tests and results are saved to this account."}
        </p>

        {error && <div className="error">{error}</div>}

        <form onSubmit={submit} className="auth-form" noValidate>
          <label>
            Username
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              minLength={mode === "register" ? 3 : 1}
              maxLength={32}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={mode === "register" ? 8 : 1}
              maxLength={128}
              required
            />
          </label>
          {mode === "register" && (
            <label>
              Confirm password
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
                required
              />
            </label>
          )}
          <button type="submit" className="primary auth-submit" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>

        {mode === "register" && (
          <p className="auth-note">
            Username: 3–32 characters (letters, numbers, dot, dash, underscore). Password: at least 8
            characters.
          </p>
        )}
      </section>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Dashboard                                                           */
/* ------------------------------------------------------------------ */

function HomeScreen({
  user,
  exams,
  onNewUpload,
  onGatePapers,
  onContinueDraft,
  onStart,
  onResume,
  onViewResult,
}: {
  user: AuthUser;
  exams: ExamHistory[];
  onNewUpload: () => void;
  onGatePapers: () => void;
  onContinueDraft: (examId: string) => void;
  onStart: (examId: string) => void;
  onResume: (attemptId: string) => void;
  onViewResult: (attemptId: string) => void;
}) {
  const attempts = exams.flatMap((exam) => exam.attempts);
  const submitted = attempts.filter((a) => a.status !== "in_progress" && a.percentage !== null);
  const best = submitted.length ? Math.max(...submitted.map((a) => a.percentage ?? 0)) : null;

  return (
    <div className="home">
      <section className="home-head">
        <div>
          <h2>Welcome, {user.username}</h2>
          <p className="muted">Your tests and previous results are saved to this account.</p>
        </div>
        <button className="primary" onClick={onNewUpload}>
          + New test from PDF
        </button>
      </section>

      <section className="home-stats">
        <div>
          <span>Tests</span>
          <strong>{exams.length}</strong>
        </div>
        <div>
          <span>Attempts</span>
          <strong>{attempts.length}</strong>
        </div>
        <div>
          <span>Completed</span>
          <strong>{submitted.length}</strong>
        </div>
        <div>
          <span>Best score</span>
          <strong>{best === null ? "—" : `${Math.round(best)}%`}</strong>
        </div>
      </section>

      <div style={{ marginBottom: 16 }}>
        <button className="ghost" onClick={onGatePapers}>
          📚 GATE Papers Library
        </button>
      </div>

      {exams.length === 0 ? (
        <div className="card empty-state">
          <h3>No tests yet</h3>
          <p className="muted">Upload your first question paper PDF to create a test.</p>
          <button className="primary" onClick={onNewUpload}>
            Upload PDF
          </button>
        </div>
      ) : (
        <section className="exam-list">
          {exams.map((exam) => (
            <article className="exam-card" key={exam.id}>
              <div className="exam-card-head">
                <div className="exam-card-title">
                  <h3>{exam.title}</h3>
                  <div className="exam-meta">
                    <span className={`badge ${exam.status}`}>{exam.status}</span>
                    <span>{exam.question_count} questions</span>
                    <span>Created {formatDate(exam.created_at)}</span>
                  </div>
                </div>
                <div className="exam-actions">
                  {exam.status === "draft" && (
                    <button className="primary" onClick={() => onContinueDraft(exam.id)}>
                      Continue editing
                    </button>
                  )}
                  {exam.status === "published" && (
                    <button className="primary" onClick={() => onStart(exam.id)}>
                      Start test
                    </button>
                  )}
                </div>
              </div>

              {exam.attempts.length > 0 && (
                <div className="attempts">
                  <div className="attempts-head">Previous attempts</div>
                  {exam.attempts.map((a) => (
                    <div className="attempt-row" key={a.attempt_id}>
                      <span className={`badge ${a.status}`}>{attemptLabel(a.status)}</span>
                      <span className="attempt-date">{formatDate(a.started_at)}</span>
                      <span className="attempt-score">
                        {a.status === "in_progress"
                          ? "In progress"
                          : `${a.score ?? 0} / ${a.max_score ?? 0} (${Math.round(a.percentage ?? 0)}%)`}
                      </span>
                      <span className="attempt-actions">
                        {a.status === "in_progress" ? (
                          <button onClick={() => onResume(a.attempt_id)}>Resume</button>
                        ) : (
                          <button onClick={() => onViewResult(a.attempt_id)}>View result</button>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </article>
          ))}
        </section>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Upload + review                                                     */
/* ------------------------------------------------------------------ */

function UploadScreen({ onUpload, onBack, uploading }: { onUpload: (f: File) => void; onBack: () => void; uploading?: boolean }) {
  const [file, setFile] = useState<File | null>(null);
  return (
    <div className="card">
      <button className="ghost" onClick={onBack}>
        ← Back to dashboard
      </button>
      <h2>Upload PDF</h2>
      <p className="muted">
        Upload a question paper PDF. We will extract the questions into an editable test.
      </p>
      <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} disabled={uploading} />
      <button className="primary" disabled={!file || uploading} onClick={() => file && onUpload(file)}>
        {uploading ? "Reading PDF (OCR may take a minute)…" : "Upload"}
      </button>
      {uploading && <p className="muted">Extracting text and parsing questions. Scanned papers take longer.</p>}
    </div>
  );
}

function ReviewScreen({
  exam,
  setExam,
  onPublish,
  onBack,
  warnings,
}: {
  exam: Exam;
  setExam: (e: Exam) => void;
  onPublish: (overrides?: { title: string; settings: any; settingsConfirmed: boolean }) => void | Promise<void>;
  onBack: () => void;
  warnings?: string[];
}) {
  const [title, setTitle] = useState(exam.title);
  const [settingsConfirmed, setSettingsConfirmed] = useState(exam.settings_confirmed);
  const [settings, setSettings] = useState(exam.settings);

  useEffect(() => {
    setTitle(exam.title);
    setSettings(exam.settings);
    setSettingsConfirmed(exam.settings_confirmed);
  }, [exam]);

  async function save() {
    const updated = await api(`/exams/${exam.id}`, {
      method: "PATCH",
      body: JSON.stringify({ title, settings, settings_confirmed: settingsConfirmed, questions: exam.questions }),
    });
    setExam(updated);
  }

  async function updateQuestion(idx: number, patch: any) {
    const qs = [...exam.questions];
    qs[idx] = { ...qs[idx], ...patch };
    const updated = await api(`/exams/${exam.id}`, {
      method: "PATCH",
      body: JSON.stringify({ questions: qs }),
    });
    setExam(updated);
  }

  async function addQuestion() {
    const qs = [
      ...exam.questions,
      {
        qtype: "single_choice",
        prompt: "New question",
        options: [
          { id: "A", text: "Option A" },
          { id: "B", text: "Option B" },
        ],
        answer_key: null,
        points: 4,
        negative_points: -1,
        topic_tags: [],
        review_status: "needs_review",
      },
    ];
    const updated = await api(`/exams/${exam.id}`, {
      method: "PATCH",
      body: JSON.stringify({ questions: qs }),
    });
    setExam(updated);
  }

  async function deleteQuestion(idx: number) {
    const qs = exam.questions.filter((_: any, i: number) => i !== idx);
    const updated = await api(`/exams/${exam.id}`, {
      method: "PATCH",
      body: JSON.stringify({ questions: qs }),
    });
    setExam(updated);
  }

  return (
    <div className="card">
      <button className="ghost" onClick={onBack}>
        ← Back to dashboard
      </button>
      <h2>Review &amp; Edit</h2>
      {warnings && warnings.length > 0 && (
        <div className="warning">
          <strong>Parsing notes</strong>
          <ul>
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}
      <label>
        Title <input value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <button onClick={save}>Save Title/Settings</button>
      <div className="settings-grid">
        <label>
          Mode
          <select value={settings.mode} onChange={(e) => setSettings({ ...settings, mode: e.target.value })}>
            <option value="exam">Exam</option>
            <option value="practice">Practice</option>
          </select>
        </label>
        <label>
          Duration (min, blank untimed)
          <input
            type="number"
            value={settings.duration_minutes ?? ""}
            onChange={(e) =>
              setSettings({ ...settings, duration_minutes: e.target.value ? Number(e.target.value) : null })
            }
          />
        </label>
        <label>
          Correct
          <input
            type="number"
            value={settings.marking.correct}
            onChange={(e) =>
              setSettings({ ...settings, marking: { ...settings.marking, correct: Number(e.target.value) } })
            }
          />
        </label>
        <label>
          Incorrect
          <input
            type="number"
            value={settings.marking.incorrect}
            onChange={(e) =>
              setSettings({ ...settings, marking: { ...settings.marking, incorrect: Number(e.target.value) } })
            }
          />
        </label>
        <label>
          Unanswered
          <input
            type="number"
            value={settings.marking.unanswered}
            onChange={(e) =>
              setSettings({ ...settings, marking: { ...settings.marking, unanswered: Number(e.target.value) } })
            }
          />
        </label>
      </div>
      <label className="confirm-row">
        <input
          type="checkbox"
          checked={settingsConfirmed}
          onChange={(e) => setSettingsConfirmed(e.target.checked)}
        />
        Confirm settings (defaults acknowledged)
      </label>
      <h3>Questions ({exam.questions.length})</h3>
      {exam.questions.map((q: any, idx: number) => (
        <div key={idx} className="qcard">
          <textarea value={q.prompt} onChange={(e) => updateQuestion(idx, { prompt: e.target.value })} />
          <select value={q.qtype} onChange={(e) => updateQuestion(idx, { qtype: e.target.value })}>
            <option value="single_choice">Single choice</option>
            <option value="multiple_select">Multiple select</option>
            <option value="numeric">Numeric</option>
          </select>
          <label>
            Points <input type="number" value={q.points} onChange={(e) => updateQuestion(idx, { points: Number(e.target.value) })} />
          </label>
          <label>
            Negative <input type="number" value={q.negative_points} onChange={(e) => updateQuestion(idx, { negative_points: Number(e.target.value) })} />
          </label>
          <label>
            Answer key{" "}
            <input
              value={JSON.stringify(q.answer_key ?? "")}
              onChange={(e) => {
                try {
                  updateQuestion(idx, { answer_key: JSON.parse(e.target.value) });
                } catch {
                  updateQuestion(idx, { answer_key: e.target.value });
                }
              }}
            />
          </label>
          <label>
            Explanation{" "}
            <textarea value={q.explanation ?? ""} onChange={(e) => updateQuestion(idx, { explanation: e.target.value })} />
          </label>
          <label>
            Source page{" "}
            <input
              type="number"
              value={q.source_page ?? ""}
              onChange={(e) => updateQuestion(idx, { source_page: e.target.value ? Number(e.target.value) : null })}
            />
          </label>
          <button onClick={() => deleteQuestion(idx)}>Delete</button>
        </div>
      ))}
      <button onClick={addQuestion}>Add Question</button>
      <br />
      <button className="primary" onClick={() => onPublish({ title, settings, settingsConfirmed: true })} disabled={!settingsConfirmed || exam.questions.length === 0}>
        Publish &amp; Start
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Exam runner                                                         */
/* ------------------------------------------------------------------ */

function RunnerScreen({
  attemptId,
  username,
  onFinish,
  onExit,
}: {
  attemptId: string;
  username: string;
  onFinish: (r: any) => void;
  onExit: () => void;
}) {
  const [attempt, setAttempt] = useState<any>(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [marked, setMarked] = useState<Record<string, boolean>>({});
  const [visited, setVisited] = useState<Record<string, boolean>>({});
  const [remaining, setRemaining] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<any>(null);
  const [saveStatus, setSaveStatus] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showInstructions, setShowInstructions] = useState(false);
  const timerRef = useRef<any>(null);
  const visitStart = useRef<number>(Date.now());

  useEffect(() => {
    (async () => {
      try {
        const a = await api(`/attempts/${attemptId}`);
        if (a.status && a.status !== "in_progress") {
          const r = await api(`/attempts/${attemptId}/results`);
          onFinish(r);
          return;
        }
        setAttempt(a);
        setAnswers(a.answers || {});
        setMarked(a.marked_for_review || {});
        setRemaining(a.time_remaining_seconds);
      } catch (e: any) {
        setLoadError(e?.message || "Could not load this test.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attemptId]);

  useEffect(() => {
    if (remaining === null) return;
    timerRef.current = setInterval(() => {
      setRemaining((r) => {
        if (r === null) return r;
        if (r <= 1) {
          clearInterval(timerRef.current);
          handleSubmit();
          return 0;
        }
        return r - 1;
      });
    }, 1000);
    return () => clearInterval(timerRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining === null]);

  useEffect(() => {
    if (!attempt) return;
    const currentId = attempt.questions[index]?.id;
    if (currentId) {
      setVisited((v) => (v[currentId] ? v : { ...v, [currentId]: true }));
    }
    setFeedback(null);
    visitStart.current = Date.now();
  }, [attempt, index]);

  async function recordVisit(qid: string) {
    const now = Date.now();
    const start = visitStart.current;
    visitStart.current = now;
    try {
      await api(`/attempts/${attemptId}/questions/${qid}/events`, {
        method: "POST",
        body: JSON.stringify({ started_at_ms: start, ended_at_ms: now }),
      });
    } catch {
      // timing events are best-effort
    }
  }

  async function saveAnswer(qid: string, response: any, mark?: boolean) {
    setSaveStatus("Saving...");
    setFeedback(null);
    try {
      const res = await api(`/attempts/${attemptId}/answers/${qid}`, {
        method: "PUT",
        body: JSON.stringify({ response, marked_for_review: mark }),
      });
      setSaveStatus("Saved");
      if (res?.feedback) setFeedback(res.feedback);
      setTimeout(() => setSaveStatus(""), 1500);
    } catch {
      setSaveStatus("Save failed");
    }
  }

  async function handleSubmit() {
    clearInterval(timerRef.current);
    try {
      await api(`/attempts/${attemptId}/submit`, { method: "POST" });
    } catch {
      // if submission already happened, the results call below still works
    }
    try {
      const r = await api(`/attempts/${attemptId}/results`);
      onFinish(r);
    } catch (e: any) {
      setLoadError(e?.message || "Could not load your results.");
    }
  }

  if (loadError) {
    return (
      <div className="card">
        <h2>Could not load this test</h2>
        <p className="error">{loadError}</p>
        <button onClick={onExit}>Back to dashboard</button>
      </div>
    );
  }
  if (!attempt) return <div className="loading">Loading test…</div>;
  const questions = attempt.questions;
  const q = questions[index];
  const qid = q.id;

  function changeAnswer(val: any) {
    const newAnswers = { ...answers, [qid]: val };
    setAnswers(newAnswers);
    saveAnswer(qid, val, marked[qid]);
  }

  async function goNext() {
    await recordVisit(qid);
    if (index < questions.length - 1) setIndex(index + 1);
  }

  const answeredCount = questions.filter((qq: any) => {
    const v = answers[qq.id];
    return v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && v.length === 0);
  }).length;

  const timeLabel =
    remaining === null
      ? "Untimed"
      : `${String(Math.floor(remaining / 3600)).padStart(2, "0")}:${String(
          Math.floor((remaining % 3600) / 60)
        ).padStart(2, "0")}:${String(remaining % 60).padStart(2, "0")}`;

  const sectionName = q.section || "General";
  const sections: string[] = Array.from(
    new Set(questions.map((qq: any) => qq.section).filter(Boolean))
  );
  const hasSections = sections.length > 1;
  const questionTypeLabel =
    q.qtype === "single_choice" ? "MCQ" : q.qtype === "multiple_select" ? "MSQ" : "NAT";

  return (
    <div className="gate">
      <div className="gate-header">
        <div className="gate-brand">
          <div className="gate-brand-mark">pdf2test</div>
        </div>
        <div className="gate-heading">
          <div className="gate-heading-main">Online Examination</div>
          <div className="gate-heading-sub">Server-backed timer and autosave</div>
        </div>
        <div className="gate-user">
          <div className="gate-user-name">{username}</div>
          <div className="gate-user-role">Candidate</div>
        </div>
      </div>

      <div className="gate-subbar">
        <div className="gate-subbar-title">{attempt.exam.title}</div>
        <div className="gate-subbar-actions">
          <button className="link" onClick={() => setShowInstructions((s) => !s)}>
            Instructions
          </button>
          <button className="link" onClick={() => setShowInstructions((s) => !s)}>
            Question Paper
          </button>
        </div>
      </div>

      {showInstructions && (
        <div className="gate-instructions">
          <strong>Instructions</strong>
          <p>
            {attempt.exam.instructions ||
              "Answer all questions. Use the palette on the right to navigate. The timer is server-backed."}
          </p>
          <button onClick={() => setShowInstructions(false)}>Close</button>
        </div>
      )}

      <div className="gate-body">
        <main className="gate-main">
          {hasSections && (
            <div className="gate-sections">
              <div className="gate-sections-label">Sections</div>
              {sections.map((s) => (
                <button
                  key={s}
                  type="button"
                  className={s === sectionName ? "gate-section active" : "gate-section"}
                  onClick={() => {
                    const firstIdx = questions.findIndex(
                      (qq: any) => (qq.section || "General") === s
                    );
                    if (firstIdx >= 0) {
                      recordVisit(qid);
                      setIndex(firstIdx);
                    }
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          <div className="gate-qmeta">
            <span>Question Type: {questionTypeLabel}</span>
            <span className="gate-marks">
              Marks for correct answer: <b>{q.points}</b> &nbsp;|&nbsp; Negative Marks:{" "}
              <b>{formatMark(q.negative_points)}</b>
            </span>
          </div>

          <div className="gate-question">
            <div className="gate-qno">Question No. {index + 1}</div>
            <div className="gate-prompt"><MathText text={q.prompt} /></div>

            {q.qtype === "single_choice" && (
              <div className="gate-options">
                {q.options.map((o: any) => (
                  <label key={o.id} className={answers[qid] === o.id ? "gate-option selected" : "gate-option"}>
                    <input
                      type="radio"
                      name={qid}
                      checked={answers[qid] === o.id}
                      onChange={() => changeAnswer(o.id)}
                    />
                    <span className="gate-option-id">{o.id}.</span>
                    <span><MathText text={o.text} /></span>
                  </label>
                ))}
              </div>
            )}

            {q.qtype === "multiple_select" && (
              <div className="gate-options">
                {q.options.map((o: any) => {
                  const arr = Array.isArray(answers[qid]) ? answers[qid] : [];
                  const checked = arr.includes(o.id);
                  return (
                    <label key={o.id} className={checked ? "gate-option selected" : "gate-option"}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => {
                          const next = e.target.checked ? [...arr, o.id] : arr.filter((x: string) => x !== o.id);
                          changeAnswer(next);
                        }}
                      />
                      <span className="gate-option-id">{o.id}.</span>
                      <span>{o.text}</span>
                    </label>
                  );
                })}
              </div>
            )}

            {q.qtype === "numeric" && (
              <div className="gate-numeric">
                <label>Your answer</label>
                <input
                  type="number"
                  value={answers[qid] ?? ""}
                  onChange={(e) => changeAnswer(e.target.value === "" ? null : Number(e.target.value))}
                />
              </div>
            )}
          </div>

          {feedback && (
            <div className={`feedback ${feedback.correct ? "correct" : "incorrect"}`}>
              <strong>{feedback.correct ? "Correct" : "Incorrect"}</strong>
              {feedback.awarded_points !== undefined && <span> — {feedback.awarded_points} points</span>}
              {feedback.explanation && (
                <p>
                  <MathText text={feedback.explanation} />
                </p>
              )}
            </div>
          )}

          <div className="gate-left-actions">
            <button
              onClick={() => {
                const m = !marked[qid];
                setMarked({ ...marked, [qid]: m });
                saveAnswer(qid, answers[qid], m);
                goNext();
              }}
            >
              Mark for Review &amp; Next
            </button>
            <button
              onClick={() => {
                setAnswers({ ...answers, [qid]: null });
                saveAnswer(qid, null, marked[qid]);
              }}
            >
              Clear Response
            </button>
            <span className={`save-status ${saveStatus.toLowerCase().replace(/\s/g, "-")}`}>{saveStatus}</span>
          </div>
        </main>

        <aside className="gate-side">
          <div className="gate-timer">
            <div className="gate-timer-label">Time Left</div>
            <div className="gate-timer-value">{timeLabel}</div>
          </div>

          <div className="gate-legend">
            <div className="legend-item">
              <span className="legend-swatch answered" /> Answered
            </div>
            <div className="legend-item">
              <span className="legend-swatch not-answered" /> Not Answered
            </div>
            <div className="legend-item">
              <span className="legend-swatch not-visited" /> Not Marked for Review
            </div>
            <div className="legend-item">
              <span className="legend-swatch answered-marked" /> Answered &amp; Marked for Review (will also be
              evaluated)
            </div>
          </div>

          <div className="gate-palette-head">
            <span>{sectionName}</span>
            <span className="palette-sub">Choose a Question</span>
          </div>
          <div className="gate-palette">
            {questions.map((qq: any, i: number) => {
              const v = answers[qq.id];
              const isAnswered =
                v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && v.length === 0);
              const isMarked = marked[qq.id];
              const isVisited = visited[qq.id];
              let cls = "not-visited";
              if (isAnswered && isMarked) cls = "answered-marked";
              else if (isAnswered) cls = "answered";
              else if (isMarked) cls = "marked";
              else if (isVisited) cls = "not-answered";
              return (
                <button
                  key={qq.id}
                  className={`palette-btn ${cls}`}
                  onClick={() => {
                    recordVisit(qid);
                    setIndex(i);
                  }}
                >
                  {i + 1}
                </button>
              );
            })}
          </div>

          <div className="gate-side-actions">
            <button
              onClick={() => {
                saveAnswer(qid, answers[qid], marked[qid]);
                goNext();
              }}
            >
              Save &amp; Next
            </button>
            <button
              className="danger"
              onClick={() => {
                if (
                  confirm(
                    `Submit test?\nAnswered ${answeredCount}/${questions.length}, Unanswered ${
                      questions.length - answeredCount
                    }`
                  )
                )
                  handleSubmit();
              }}
            >
              Submit
            </button>
          </div>
        </aside>
      </div>

      <div className="gate-footer">
        <span>Version: 1.0.0</span>
        <span>Server time is authoritative</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* GATE Papers Library                                                 */
/* ------------------------------------------------------------------ */

function GatePapersScreen({ onBack, onStartExam }: { onBack: () => void; onStartExam: (id: string) => void }) {
  const [branches, setBranches] = useState<any[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<string>("CS");
  const [papers, setPapers] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const b = await (await import("./api")).fetchGateBranches();
        setBranches(b);
      } catch (e: any) {
        setError(e?.message || "Could not load branches.");
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const p = await (await import("./api")).fetchGatePapers(selectedBranch);
        setPapers(p);
      } catch (e: any) {
        setError(e?.message || "Could not load papers.");
      } finally {
        setLoading(false);
      }
    })();
  }, [selectedBranch]);

  return (
    <div className="card">
      <button className="ghost" onClick={onBack}>
        ← Back to dashboard
      </button>
      <h2>GATE Previous Papers Library</h2>
      <p className="muted">
        Browse GATE previous year question papers by branch. Upload a paper PDF to create a practice test.
      </p>

      <div className="settings-grid" style={{ marginBottom: 16 }}>
        <label>
          Branch
          <select value={selectedBranch} onChange={(e) => setSelectedBranch(e.target.value)}>
            {branches.map((b: any) => (
              <option key={b.code} value={b.code}>
                {b.code} — {b.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <div className="error">{error}</div>}

      {loading ? (
        <div className="loading">Loading papers…</div>
      ) : papers.length === 0 ? (
        <div className="empty-state">
          <p className="muted">No papers registered for this branch yet. Upload a GATE paper PDF to get started.</p>
        </div>
      ) : (
        <div className="exam-list">
          {papers.map((p: any) => (
            <article className="exam-card" key={p.id}>
              <div className="exam-card-head">
                <div className="exam-card-title">
                  <h3>{p.title}</h3>
                  <div className="exam-meta">
                    <span className="badge">{p.year}</span>
                    <span>{p.paper_type}</span>
                    <span>{p.question_count ? `${p.question_count} questions` : "—"}</span>
                    {p.has_solutions && <span className="badge">Solutions</span>}
                  </div>
                </div>
                <div className="exam-actions">
                  {p.exam_id && (
                    <button className="primary" onClick={() => onStartExam(p.exam_id)}>
                      Start test
                    </button>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Results                                                             */
/* ------------------------------------------------------------------ */

function ResultsScreen({ results, onBack }: { results: any; onBack: () => void }) {
  const topics = useMemo(() => {
    const map = new Map<string, { name: string; total: number; correct: number; incorrect: number; unanswered: number; score: number; max: number; time: number }>();
    for (const q of results.questions || []) {
      const tag = (q.topic_tags && q.topic_tags[0]) || "General";
      if (!map.has(tag)) map.set(tag, { name: tag, total: 0, correct: 0, incorrect: 0, unanswered: 0, score: 0, max: 0, time: 0 });
      const t = map.get(tag)!;
      t.total += 1;
      t.max += q.points || 0;
      t.score += q.awarded_points || 0;
      t.time += q.time_spent_seconds || 0;
      if (q.user_response === null || q.user_response === undefined || q.user_response === "" || (Array.isArray(q.user_response) && q.user_response.length === 0)) {
        t.unanswered += 1;
      } else if (q.is_correct) {
        t.correct += 1;
      } else {
        t.incorrect += 1;
      }
    }
    return Array.from(map.values())
      .map((t) => ({ ...t, pct: t.max ? Math.round((t.score / t.max) * 100) : 0 }))
      .sort((a, b) => b.pct - a.pct);
  }, [results]);

  const strongest = topics.length ? topics[0] : null;
  const weakest = topics.length > 1 ? topics[topics.length - 1] : null;

  return (
    <div className="card">
      <button className="ghost" onClick={onBack}>
        ← Back to dashboard
      </button>
      <h2>Results</h2>
      <p className="muted">
        {results.exam_title} · submitted {formatDate(results.submitted_at)}
      </p>
      <div className="result-summary">
        <div>
          <span>Score</span>
          <strong>
            {results.score} / {results.max_score}
          </strong>
        </div>
        <div>
          <span>Percentage</span>
          <strong>{results.percentage}%</strong>
        </div>
        <div>
          <span>Correct</span>
          <strong>{results.correct_count}</strong>
        </div>
        <div>
          <span>Incorrect</span>
          <strong>{results.incorrect_count}</strong>
        </div>
        <div>
          <span>Unanswered</span>
          <strong>{results.unanswered_count}</strong>
        </div>
        <div>
          <span>Total time</span>
          <strong>{Math.round(results.total_time_seconds)}s</strong>
        </div>
      </div>
      <h3>Topic Analysis</h3>
      {topics.length > 0 && (
        <div className="topic-analysis">
          <div className="topic-summary">
            {strongest && (
              <div className="topic-highlight strong">
                <span>Strongest</span>
                <strong>{strongest.name}</strong>
                <em>{strongest.pct}%</em>
              </div>
            )}
            {weakest && weakest.name !== strongest?.name && (
              <div className="topic-highlight weak">
                <span>Needs work</span>
                <strong>{weakest.name}</strong>
                <em>{weakest.pct}%</em>
              </div>
            )}
          </div>
          <div className="topic-bars">
            {topics.map((t) => (
              <div className="topic-bar-row" key={t.name}>
                <div className="topic-bar-label">{t.name}</div>
                <div className="topic-bar-track">
                  <div
                    className={`topic-bar-fill ${t.pct >= 70 ? "good" : t.pct >= 40 ? "mid" : "bad"}`}
                    style={{ width: `${Math.max(4, t.pct)}%` }}
                  />
                </div>
                <div className="topic-bar-stats">
                  {t.correct}/{t.total} · {t.score}/{t.max} pts · {t.pct}%
                </div>
              </div>
            ))}
          </div>
          <table className="topic-table">
            <thead>
              <tr>
                <th>Topic</th>
                <th>Qs</th>
                <th>Correct</th>
                <th>Incorrect</th>
                <th>Unanswered</th>
                <th>Score</th>
                <th>Max</th>
                <th>%</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {topics.map((t) => (
                <tr key={t.name}>
                  <td>{t.name}</td>
                  <td>{t.total}</td>
                  <td>{t.correct}</td>
                  <td>{t.incorrect}</td>
                  <td>{t.unanswered}</td>
                  <td>{t.score}</td>
                  <td>{t.max}</td>
                  <td>{t.pct}%</td>
                  <td>{Math.round(t.time)}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3>Review</h3>
      {results.questions.map((q: any, i: number) => (
        <div key={q.id} className="qcard">
          <p>
            {i + 1}. <MathText text={q.prompt} />
          </p>
          <p>
            Your answer: {JSON.stringify(q.user_response)} | Correct: {JSON.stringify(q.answer_key)} |{" "}
            {q.is_correct ? "✓" : "✗"} | Points: {q.awarded_points}
          </p>
          {q.explanation && <p>Explanation: <MathText text={q.explanation} /></p>}
          <p>Time spent: {q.time_spent_seconds}s</p>
        </div>
      ))}
    </div>
  );
}
