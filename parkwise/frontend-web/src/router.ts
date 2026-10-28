import { isAuthenticated, role } from "./auth";
export type Route = "admin" | "user";
export function route(): Route { return location.pathname === "/user" || location.pathname === "/entry" || location.pathname === "/exit" ? "user" : "admin"; }
export function go(target: string) { history.pushState({}, "", (target === "user" || target === "overview" ? "/user" : "/admin") + location.search); window.dispatchEvent(new PopStateEvent("popstate")); }
export function isAdmin() { return role() === "ADMIN"; }
export function canAccess(target: string) { return target === "admin" ? isAdmin() : target === "user" && role() !== "ADMIN"; }
export function guard() { return isAuthenticated() && canAccess(route()); }
export function visiblePages() { return [route()]; }
