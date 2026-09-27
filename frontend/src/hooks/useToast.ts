import { createContext, useContext } from "react";

export type ToastKind = "info" | "success" | "error";

export type ToastItem = {
  id: number;
  kind: ToastKind;
  title: string;
  body: string;
};

type ToastContextValue = {
  toasts: ToastItem[];
  push: (kind: ToastKind, title: string, body: string) => void;
  dismiss: (id: number) => void;
};

export const ToastContext = createContext<ToastContextValue | null>(null);

export const useToast = () => {
  const value = useContext(ToastContext);
  if (!value) {
    throw new Error("useToast must be used inside ToastProvider");
  }
  return value;
};
