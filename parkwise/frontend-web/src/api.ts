import type { Availability, Facility, Gate, Metrics, Prediction, ScanEvent, Scanner, ScannerSummary, Ticket, Tokens, Vehicle, Zone, Slot, ExitResult, User } from "./types";

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
      try { const body = await response.json(); message = body?.error?.message || body?.detail || message; } catch { /* safe fallback */ }
      throw new ApiError(response.status, message);
    }
    if (response.status === 204) return undefined as T;
    const type = response.headers.get("content-type") || "";
    if (type.includes("json")) return await response.json() as T;
    if (type.includes("spreadsheetml") || type.includes("octet-stream")) return await response.blob() as T;
    return await response.text() as T;
  } catch (error) { if (error instanceof ApiError) throw error; throw new ApiError(0, "The PARKWISE API is unavailable."); }
  finally { window.clearTimeout(timer); }
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });
export const api = {
  login: (username: string, password: string) => request<Tokens>("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({ username, password }) }),
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
  exportCsv: (days: number) => request<string>(`/api/reports/export-csv?days=${days}`),
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
  exportXlsx: (days: number) => request<Blob>(`/api/reports/export-xlsx?days=${days}`, { headers: { Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" } }),
};
