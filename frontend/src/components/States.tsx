type EmptyStateProps = {
  title: string;
  body: string;
};

export const EmptyState = ({ title, body }: EmptyStateProps) => (
  <div className="rounded-xl border border-dashed border-[var(--line)] bg-white px-8 py-16 text-center">
    <p className="text-lg">{title}</p>
    <p className="mx-auto mt-2 max-w-md font-sans text-sm leading-6 text-[var(--muted)]">{body}</p>
  </div>
);

export const LoadingState = ({ label = "Loading…" }: { label?: string }) => (
  <div className="rounded-xl border border-[var(--line)] bg-white px-8 py-16 text-center font-sans text-sm text-[var(--muted)]">
    {label}
  </div>
);

export const ErrorState = ({ message }: { message: string }) => (
  // Hex for Tailwind's red-200 / red-50: their oklch() values don't render on the
  // Windows 7 build (Electron 22 = Chromium 108).
  <div className="rounded-xl border border-[#fecaca] bg-[#fef2f2] px-8 py-10 text-center">
    <p className="text-lg text-[var(--danger)]">Something went wrong</p>
    <p className="mt-2 font-sans text-sm text-[var(--muted)]">{message}</p>
  </div>
);
