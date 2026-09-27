import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiClient, type AuthStatusResponse, type LoginPayload, type RegisterPayload } from "../services/api.ts";
import { normalizeTheme, useTheme } from "./ThemeProvider.tsx";

/** loading = checking API; guest = show login/register; ready = main app */
type AuthPhase = "loading" | "guest" | "ready";

/** Which guest screen to show. Login is always the default entry. */
type GuestView = "login" | "register";

type AuthContextValue = {
  phase: AuthPhase;
  guestView: GuestView;
  status: AuthStatusResponse | null;
  error: string;
  canRegister: boolean;
  refresh: () => Promise<void>;
  showLogin: () => void;
  showRegister: () => void;
  register: (payload: RegisterPayload) => Promise<void>;
  login: (payload: LoginPayload) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const resolvePhase = (payload: AuthStatusResponse): AuthPhase =>
  payload.authenticated ? "ready" : "guest";

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const { setTheme } = useTheme();
  const [phase, setPhase] = useState<AuthPhase>("loading");
  const [guestView, setGuestView] = useState<GuestView>("login");
  const [status, setStatus] = useState<AuthStatusResponse | null>(null);
  const [error, setError] = useState("");

  const applyStatus = useCallback(
    (payload: AuthStatusResponse) => {
      setStatus(payload);
      setPhase(resolvePhase(payload));
      // After a successful registration/login we land in the app; otherwise stay on login.
      if (payload.authenticated) {
        setGuestView("login");
      }
      if (payload.shop?.ui_theme) {
        setTheme(normalizeTheme(payload.shop.ui_theme));
      }
    },
    [setTheme],
  );

  const refresh = useCallback(async () => {
    setError("");
    try {
      const payload = await apiClient.getAuthStatus();
      applyStatus(payload);
    } catch (caught) {
      setPhase("loading");
      setError(caught instanceof Error ? caught.message : "Unable to reach the local API.");
    }
  }, [applyStatus]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const showLogin = useCallback(() => {
    setError("");
    setGuestView("login");
  }, []);

  const showRegister = useCallback(() => {
    setError("");
    setGuestView("register");
  }, []);

  const register = useCallback(
    async (payload: RegisterPayload) => {
      setError("");
      try {
        const next = await apiClient.registerShop(payload);
        applyStatus(next);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Registration failed.");
        throw caught;
      }
    },
    [applyStatus],
  );

  const login = useCallback(
    async (payload: LoginPayload) => {
      setError("");
      try {
        const next = await apiClient.login(payload);
        applyStatus(next);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Sign in failed.");
        throw caught;
      }
    },
    [applyStatus],
  );

  const logout = useCallback(async () => {
    setError("");
    setGuestView("login");
    await apiClient.logout();
    await refresh();
  }, [refresh]);

  const canRegister = !(status?.registered ?? false);

  const value = useMemo(
    () => ({
      phase,
      guestView,
      status,
      error,
      canRegister,
      refresh,
      showLogin,
      showRegister,
      register,
      login,
      logout,
    }),
    [phase, guestView, status, error, canRegister, refresh, showLogin, showRegister, register, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
};
