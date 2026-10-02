import { isAuthenticated, role } from "./auth";
export type Route = "overview" | "recommendations" | "live-map" | "entry" | "exit" | "find-vehicle" | "vehicles" | "places" | "layout" | "reports" | "predictions" | "feedback" | "operations" | "scanner-console" | "admin";
const rolePages: Record<string, string[]> = { ADMIN: ["overview", "recommendations", "live-map", "entry", "exit", "find-vehicle", "vehicles", "places", "layout", "reports", "predictions", "feedback", "operations", "scanner-console", "admin"], ATTENDANT: ["overview", "live-map", "entry", "exit", "scanner-console", "feedback"], STUDENT: ["overview", "recommendations", "live-map", "vehicles", "entry", "exit", "find-vehicle", "feedback"], STAFF: ["overview", "recommendations", "live-map", "vehicles", "entry", "exit", "find-vehicle", "feedback"], VISITOR: ["overview", "live-map"] };
export function route(): Route { const raw = location.pathname.replace(/^\//, "") || "overview"; return (raw === "" ? "overview" : raw) as Route; }
export function canAccess(target: string) { const r = role(); return Boolean(r && rolePages[r]?.includes(target)); }
export function go(target: string) { history.pushState({}, "", target === "overview" ? "/" : `/${target}`); window.dispatchEvent(new PopStateEvent("popstate")); }
export function guard() { if (!isAuthenticated() && location.pathname !== "/login") { go("login"); return false; } if (isAuthenticated() && location.pathname === "/login") { go("overview"); return false; } return true; }
export const visiblePages = () => rolePages[role() || ""] || [];
