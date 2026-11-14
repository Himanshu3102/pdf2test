const BASE = "/api/v1";
const TOKEN_KEY = "exam_app_token";

export interface AuthUser {
  id: string;
  username: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface AttemptSummary {
  attempt_id: string;
  status: string;
  started_at: string;
  submitted_at: string | null;
  score: number | null;
  max_score: number | null;
  percentage: number | null;
}

export interface ExamHistory {
  id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
  question_count: number;
  attempts: AttemptSummary[];
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function errorMessage(text: string, fallback: string): string {
  if (!text) return fallback;
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail) && parsed.detail[0]?.msg) return parsed.detail[0].msg;
  } catch {
    // not JSON, use raw text below
  }
  return text;
}

export async function api(path: string, opts: RequestInit = {}) {
  const res = await fetch(BASE + path, {
    ...opts,
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    if (res.status === 401 && getToken()) {
      clearToken();
      window.dispatchEvent(new Event("exam:logout"));
    }
    throw new ApiError(errorMessage(text, res.statusText), res.status);
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function uploadPdf(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(BASE + "/exams/upload", {
    method: "POST",
    headers: authHeaders(),
    body: fd,
  });
  if (!res.ok) {
    const text = await res.text();
    if (res.status === 401 && getToken()) {
      clearToken();
      window.dispatchEvent(new Event("exam:logout"));
    }
    throw new ApiError(errorMessage(text, res.statusText), res.status);
  }
  return res.json();
}
