import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

/** Theme ids persisted on ApplicationSettings.ui_theme and mirrored in localStorage. */
export type UiTheme = "midnight" | "slate" | "paper";

export const UI_THEMES: { id: UiTheme; label: string; blurb: string }[] = [
  { id: "midnight", label: "Midnight", blurb: "Dark charcoal with teal accents — default for long counter days." },
  { id: "slate", label: "Slate", blurb: "Cool blue-gray dark theme." },
  { id: "paper", label: "Paper", blurb: "Light desk look for bright shops." },
];

const STORAGE_KEY = "shopmanager.ui_theme";

const isTheme = (value: string | null | undefined): value is UiTheme =>
  value === "midnight" || value === "slate" || value === "paper";

const readStoredTheme = (): UiTheme => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return isTheme(raw) ? raw : "midnight";
  } catch {
    return "midnight";
  }
};

const applyThemeToDocument = (theme: UiTheme) => {
  document.documentElement.setAttribute("data-theme", theme);
};

type ThemeContextValue = {
  theme: UiTheme;
  setTheme: (theme: UiTheme) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export const ThemeProvider = ({ children }: { children: ReactNode }) => {
  const [theme, setThemeState] = useState<UiTheme>(() => {
    const initial = readStoredTheme();
    applyThemeToDocument(initial);
    return initial;
  });

  const setTheme = useCallback((next: UiTheme) => {
    setThemeState(next);
    applyThemeToDocument(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* localStorage may be unavailable in locked-down webviews */
    }
  }, []);

  useEffect(() => {
    applyThemeToDocument(theme);
  }, [theme]);

  const value = useMemo(() => ({ theme, setTheme }), [theme, setTheme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
};

/** Sync a shop theme from the API into the provider + local cache. */
export const normalizeTheme = (value: string | null | undefined): UiTheme =>
  isTheme(value) ? value : "midnight";
