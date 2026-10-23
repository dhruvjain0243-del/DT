import type { Role, Tokens, User } from "./types";
import { api, authToken, clearTokens, saveTokens } from "./api";
import { supabase } from "./lib/supabase";

export function currentUser(): User | null { const value = sessionStorage.getItem("parkwise_user"); return value ? JSON.parse(value) as User : null; }
export function isAuthenticated() { return Boolean(authToken() && currentUser()); }
export function role(): Role | null { return currentUser()?.role || null; }
export function setSession(tokens: Tokens) { saveTokens(tokens); sessionStorage.setItem("parkwise_user", JSON.stringify(tokens.user)); }
export async function signIn(username: string, password: string) { const tokens = await api.login(username, password); setSession(tokens); }
export async function signInWithSupabase(email: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error || !data.session) throw new Error(error?.message || "Unable to create a Supabase session");
  const tokens = await api.supabaseSession(data.session.access_token);
  setSession(tokens);
}
export async function signUpWithSupabase(email: string, password: string, fullName: string) {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: { data: { full_name: fullName }, emailRedirectTo: `${window.location.origin}/auth/callback` },
  });
  if (error) throw new Error(error.message);
  return data;
}
export async function bridgeSupabaseSession() {
  const { data } = await supabase.auth.getSession();
  if (!data.session) return false;
  const tokens = await api.supabaseSession(data.session.access_token);
  setSession(tokens);
  return true;
}
export async function resendSupabaseVerification(email: string) {
  const { error } = await supabase.auth.resend({ type: "signup", email, options: { emailRedirectTo: `${window.location.origin}/auth/callback` } });
  if (error) throw new Error(error.message);
}
export async function signOut() { try { if (authToken()) await api.logout(); } catch { /* local session still clears */ } await supabase.auth.signOut(); clearTokens(); sessionStorage.removeItem("parkwise_user"); }
