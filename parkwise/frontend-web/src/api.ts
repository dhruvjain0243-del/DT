import type { Availability, Facility, Gate, Metrics, Prediction, ScanEvent, Scanner, ScannerSummary, Ticket, Tokens, Vehicle, Zone, Slot, ExitResult, User, CollegeFacility, CollegeProfile, CollegeSession, CollegeAction, CollegeQr, LocationReport } from "./types";

const base = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

let accessToken = sessionStorage.getItem("parkwise_access_token");
let refreshToken = sessionStorage.getItem("parkwise_refresh_token");
export const authToken = () => accessToken;
export function saveTokens(tokens: Tokens) { accessToken = tokens.access_token; refreshToken = tokens.refresh_token; sessionStorage.setItem("parkwise_access_token", accessToken); sessionStorage.setItem("parkwise_refresh_token", refreshToken); }
export function clearTokens() { accessToken = null; refreshToken = null; sessionStorage.removeItem("parkwise_access_token"); sessionStorage.removeItem("parkwise_refresh_token"); }

async function request<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body && !(options.body instanceof URLSearchParams) && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`${base}${path}`, { ...options, headers, signal: controller.signal });
    if (response.status === 401 && retry && refreshToken) {
      const refreshed = await fetch(`${base}/api/auth/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: refreshToken }) });
      if (refreshed.ok) { saveTokens(await refreshed.json() as Tokens); return request<T>(path, options, false); }
      clearTokens();
    }
    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try { const body = await response.json(); const details = body?.error?.details?.map((item: { field?: string; message?: string }) => `${item.field || "field"}: ${item.message || "invalid value"}`).join("; "); message = details || body?.error?.message || body?.detail || message; } catch { /* safe fallback */ }
      throw new ApiError(response.status, message);
    }
    if (response.status === 204) return undefined as T;
    const type = response.headers.get("content-type") || "";
    if (type.includes("json")) return await response.json() as T;
    if (type.includes("spreadsheetml") || type.includes("octet-stream") || type.startsWith("image/")) return await response.blob() as T;
    return await response.text() as T;
  } catch (error) { if (error instanceof ApiError) throw error; throw new ApiError(0, "The PARKWISE API is unavailable."); }
  finally { window.clearTimeout(timer); }
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });
export const api = {
  forgotPassword: (email: string) => request<{message: string}>("/api/auth/forgot-password", json("POST", {email})),
  resetPassword: (token: string, password: string) => request<{message: string}>("/api/auth/reset-password", json("POST", {token, password})),
  demoSession: (role: "ADMIN" | "STUDENT") => request<Tokens>("/api/auth/demo-session", json("POST", { role })),
  login: (username: string, password: string) => request<Tokens>("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({ username, password }) }),
  supabaseSession: (accessToken: string, body: { full_name?: string | null; phone?: string | null } = {}) => request<Tokens>("/api/auth/supabase-session", { method: "POST", headers: { Authorization: `Bearer ${accessToken}` }, body: JSON.stringify(body) }),
  logout: () => request<void>("/api/auth/logout", json("POST", { refresh_token: refreshToken })),
  me: () => request<User>("/api/auth/me"),
  facilities: () => request<Facility[]>("/api/facilities"),
  createFacility: (body: { name: string; address: string; total_capacity: number; latitude?: number | null; longitude?: number | null; distance_km?: number; price_per_hour?: number }) => request<Facility>("/api/facilities", json("POST", body)),
  availability: () => request<Availability[]>("/api/availability"),
  vehicles: () => request<Vehicle[]>("/api/vehicles/mine"),
  addVehicle: (body: { registration_number: string; vehicle_type: string }) => request<Vehicle>("/api/vehicles", json("POST", body)),
  zones: (facilityId: number) => request<Zone[]>(`/api/facilities/${facilityId}/zones`),
  slots: (zoneId: number) => request<Slot[]>(`/api/zones/${zoneId}/slots`),
  entry: (body: unknown) => request<Ticket>("/api/parking/entry", json("POST", body)),
  exit: (body: unknown) => request<ExitResult>("/api/parking/exit", json("POST", body)),
  activeTicket: () => request<Ticket>("/api/parking/my-active-session"),
  history: () => request<unknown[]>("/api/parking/my-history"),
  findVehicle: (ticketId: string) => request<unknown>(`/api/parking/find-my-vehicle/${encodeURIComponent(ticketId)}`),
  predictions: () => request<Prediction[]>("/api/predictions/latest"),
  metrics: () => request<Metrics>("/api/predictions/metrics"),
  runPredictions: () => request<unknown>("/api/predictions/run", json("POST", {})),
  dailyReport: (days: number) => request<unknown[]>(`/api/reports/daily?days=${days}`),
  peakReport: (days: number) => request<unknown[]>(`/api/reports/peak-hours?days=${days}`),
  sessionsReport: (days: number) => request<unknown[]>(`/api/reports/sessions?days=${days}`),
  exportCsv: (_days: number, facilityId?: number, date?: string) => request<string>(`/api/reports/export-csv?facility_id=${facilityId || ""}&selected_date=${date || ""}`),
  feedback: (body: unknown) => request<unknown>("/api/feedback", json("POST", body)),
  users: () => request<User[]>("/api/users"),
  audits: () => request<unknown[]>("/api/audit-logs?limit=50"),
  gates: (facilityId: number) => request<Gate[]>(`/api/operations/facilities/${facilityId}/gates`),
  createGate: (facilityId: number, body: { name: string; gate_type: string; is_active: boolean }) => request<Gate>(`/api/operations/facilities/${facilityId}/gates`, json("POST", body)),
  scanners: (gateId: number) => request<Scanner[]>(`/api/operations/gates/${gateId}/scanners`),
  createScanner: (gateId: number, body: { name: string; device_identifier: string; is_active: boolean }) => request<Scanner>(`/api/operations/gates/${gateId}/scanners`, json("POST", body)),
  scanEvents: (limit = 100) => request<ScanEvent[]>(`/api/operations/scan-events?limit=${limit}`),
  revokeScanner: (scannerId: number) => request<Scanner>(`/api/operations/scanners/${scannerId}/revoke`, json("POST", {})),
  regenerateScanner: (scannerId: number) => request<Scanner>(`/api/operations/scanners/${scannerId}/regenerate`, json("POST", {})),
  scannerScan: (scannerId: number, apiKey: string, body: { scan_type: string; qr_token?: string; vehicle_registration?: string; scan_reference?: string }) => request<Record<string, unknown>>(`/api/operations/scanners/${scannerId}/scan`, { method: "POST", headers: { "X-Scanner-Key": apiKey }, body: JSON.stringify(body) }),
  scannerSummary: (days = 30) => request<ScannerSummary[]>(`/api/reports/scanner-summary?days=${days}`),
  exportXlsx: (_days: number, facilityId?: number, date?: string) => request<Blob>(`/api/reports/export-xlsx?facility_id=${facilityId || ""}&selected_date=${date || ""}`, { headers: { Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" } }),
  locations: () => request<CollegeFacility[]>("/api/college/locations"),
  locationReport: (facilityId: number, date: string) => request<LocationReport>(`/api/reports/location-records?facility_id=${facilityId}&selected_date=${date}`),
  addLocation: (body: unknown) => request<CollegeFacility>("/api/college/admin/locations", json("POST", body)),
  collegeFacility: (facilityId?: number) => request<CollegeFacility>(`/api/college/facility${facilityId ? `?facility_id=${facilityId}` : ""}`),
  collegeProfile: () => request<CollegeProfile>("/api/college/profile"),
  updateCollegeProfile: (body: { full_name: string; phone?: string | null; registration_number: string }) => request<CollegeProfile>("/api/college/profile", json("PUT", body)),
  collegeEntry: (facilityId?: number) => request<CollegeAction>(`/api/college/entry${facilityId ? `?facility_id=${facilityId}` : ""}`, json("POST", {})),
  collegeExit: (facilityId?: number) => request<CollegeAction>(`/api/college/exit${facilityId ? `?facility_id=${facilityId}` : ""}`, json("POST", {})),
  collegeHistory: (facilityId?: number) => request<CollegeSession[]>(`/api/college/my-sessions${facilityId ? `?facility_id=${facilityId}` : ""}`),
  collegeAdminSessions: (facilityId?: number) => request<CollegeSession[]>(`/api/college/admin/sessions${facilityId ? `?facility_id=${facilityId}` : ""}`),
  collegeConfig: (body: { name: string; address: string; latitude: number | null; longitude: number | null; capacity: number; timezone: string; permitted_email_domains: string[] }, facilityId?: number) => request<CollegeFacility>(`/api/college/admin/config${facilityId ? `?facility_id=${facilityId}` : ""}`, json("PUT", body)),
  collegeQrImage: (direction: "entry" | "exit", facilityId?: number) => request<Blob>(`/api/college/qr/${direction}.png${facilityId ? `?facility_id=${facilityId}` : ""}`),
  collegeQr: (facilityId?: number) => request<CollegeQr>(`/api/college/qr${facilityId ? `?facility_id=${facilityId}` : ""}`),
  requestEmailVerification: (email: string) => request<{ message: string }>(`/api/auth/verify-email/request?email=${encodeURIComponent(email)}`, { method: "POST" }),
  register: (body: { full_name: string; email: string; phone?: string | null; password: string; role: string }) => request<User>("/api/auth/register", json("POST", body)),
};
