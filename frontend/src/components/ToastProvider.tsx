import { useMemo, useState, type ReactNode } from "react";
import { ToastContext, type ToastItem, type ToastKind } from "../hooks/useToast";

type ToastProviderProps = {
  children: ReactNode;
};

export const ToastProvider = ({ children }: ToastProviderProps) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const value = useMemo(
    () => ({
      toasts,
      push: (kind: ToastKind, title: string, body: string) => {
        const id = Date.now();
        setToasts((current) => [...current, { id, kind, title, body }]);
        window.setTimeout(() => {
          setToasts((current) => current.filter((item) => item.id !== id));
        }, 4200);
      },
      dismiss: (id: number) => {
        setToasts((current) => current.filter((item) => item.id !== id));
      },
    }),
    [toasts],
  );

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
};
