// Auth state: token lives in secure storage (Keychain/EncryptedSharedPreferences
// on native), user profile comes from /auth/me. DB is authoritative.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";

import { api, apiBase, getToken, setToken } from "@/src/api";
import { queryClient } from "@/src/query-client";

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: string;
  company_id: string | null;
  company?: { id: string; name: string; segment?: string | null };
}

interface AuthContextValue {
  status: "loading" | "signedOut" | "signedIn";
  user: AuthUser | null;
  login: (email: string, password: string) => Promise<AuthUser | null>;
  register: (name: string, email: string, password: string) => Promise<AuthUser | null>;
  socialLogin: (provider: "google" | "instagram") => Promise<AuthUser | null>;
  logout: () => Promise<void>;
  refresh: () => Promise<AuthUser | null>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthContextValue["status"]>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  const refresh = useCallback(async (): Promise<AuthUser | null> => {
    try {
      const token = await getToken();
      if (!token) {
        setUser(null);
        setStatus("signedOut");
        return null;
      }
      const me = await api<AuthUser>("/auth/me");
      setUser(me);
      setStatus("signedIn");
      return me;
    } catch {
      await setToken(null).catch(() => undefined);
      queryClient.clear();
      setUser(null);
      setStatus("signedOut");
      return null;
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: { email, password },
    });
    await queryClient.cancelQueries();
    queryClient.clear();
    await setToken(data.access_token);
    return refresh();
  }, [refresh]);

  const register = useCallback(async (name: string, email: string, password: string) => {
    const data = await api<{ access_token: string }>("/auth/register", {
      method: "POST",
      body: { name, email, password },
    });
    await queryClient.cancelQueries();
    queryClient.clear();
    await setToken(data.access_token);
    return refresh();
  }, [refresh]);

  const socialLogin = useCallback(async (provider: "google" | "instagram") => {
    const returnUrl = Linking.createURL("oauth/callback");
    const startUrl = `${apiBase()}/auth/social/${provider}/start?return_url=${encodeURIComponent(returnUrl)}`;
    const result = await WebBrowser.openAuthSessionAsync(startUrl, returnUrl);
    if (result.type !== "success" || !result.url) {
      if (result.type === "cancel" || result.type === "dismiss") return null;
      throw new Error("Não foi possível concluir o login social.");
    }
    const parsed = Linking.parse(result.url);
    const error = typeof parsed.queryParams?.error === "string" ? parsed.queryParams.error : null;
    if (error) throw new Error("O provedor não concluiu a autorização. Tente novamente.");
    const code = typeof parsed.queryParams?.code === "string" ? parsed.queryParams.code : null;
    if (!code) throw new Error("O login social não retornou um código válido.");
    const data = await api<{ access_token: string }>("/auth/social/exchange", {
      method: "POST",
      body: { code },
    });
    await queryClient.cancelQueries();
    queryClient.clear();
    await setToken(data.access_token);
    return refresh();
  }, [refresh]);

  const logout = useCallback(async () => {
    await setToken(null);
    await queryClient.cancelQueries();
    queryClient.clear();
    setUser(null);
    setStatus("signedOut");
  }, []);

  const value = useMemo(
    () => ({ status, user, login, register, socialLogin, logout, refresh }),
    [status, user, login, register, socialLogin, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth deve ser usado dentro de AuthProvider");
  return ctx;
}
