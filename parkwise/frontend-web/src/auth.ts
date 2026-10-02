import type { Role, Tokens, User } from "./types";
import { api, authToken, clearTokens, saveTokens } from "./api";

export function currentUser(): User | null { const value = sessionStorage.getItem("parkwise_user"); return value ? JSON.parse(value) as User : null; }
export function isAuthenticated() { return Boolean(authToken() && currentUser()); }
export function role(): Role | null { return currentUser()?.role || null; }
export function setSession(tokens: Tokens) { saveTokens(tokens); sessionStorage.setItem("parkwise_user", JSON.stringify(tokens.user)); }
export async function signIn(username: string, password: string) { const tokens = await api.login(username, password); setSession(tokens); }
export async function signOut() { try { if (authToken()) await api.logout(); } catch { /* local session still clears */ } clearTokens(); sessionStorage.removeItem("parkwise_user"); }
