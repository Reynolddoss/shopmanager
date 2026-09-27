import { useToast } from "../hooks/useToast";

export const ToastViewport = () => {
  const { toasts, dismiss } = useToast();
  return (
    <div className="pointer-events-none fixed right-6 bottom-6 z-50 flex w-80 flex-col gap-2">
      {toasts.map((toast) => (
        <button
          key={toast.id}
          type="button"
          className="pointer-events-auto rounded-lg border border-[var(--line)] bg-[var(--panel)] p-3 text-left shadow-[var(--shadow)]"
          onClick={() => dismiss(toast.id)}
        >
          <p className="font-sans text-xs tracking-wide text-[var(--muted)] uppercase">{toast.kind}</p>
          <p className="mt-1 text-sm font-medium">{toast.title}</p>
          <p className="mt-1 font-sans text-sm text-[var(--muted)]">{toast.body}</p>
        </button>
      ))}
    </div>
  );
};
