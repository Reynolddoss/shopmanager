import { EmptyState } from "../components/States.tsx";

type PlaceholderPageProps = {
  title: string;
  body: string;
};

export const PlaceholderPage = ({ title, body }: PlaceholderPageProps) => (
  <section>
    <h2 className="text-3xl">{title}</h2>
    <p className="mt-2 max-w-2xl font-sans text-sm leading-6 text-[var(--muted)]">{body}</p>
    <div className="mt-8">
      <EmptyState title="Not in Phase 1" body="This workspace is a shell so navigation and layout can be judged now. Business workflows arrive in later phases." />
    </div>
  </section>
);
