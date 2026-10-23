import { currentUser } from "./auth";
import { isAuthenticated, role } from "./auth";
export type Route = string;
export function route(): Route { return location.pathname === "/admin" ? "admin" : "overview"; }
export function go(target: Route) { history.pushState({}, "", target === "login" ? "/login" : target === "admin" ? "/admin" : "/"); window.dispatchEvent(new PopStateEvent("popstate")); }
export function isAdmin() { return currentUser()?.role === "ADMIN"; }
export function canAccess(target: string) { return target === "overview" || target === "admin"; }
export function guard() { if (!isAuthenticated() && location.pathname !== "/login") { go("login"); return false; } return true; }
export function visiblePages() { return role() === "ADMIN" ? ["overview", "admin"] : ["overview"]; }
