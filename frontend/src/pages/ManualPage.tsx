import { useEffect, useState } from "react";
import { MANUAL_PAGES, type ManualPage } from "./manual/manualPages.ts";

const chapters = Array.from(new Set(MANUAL_PAGES.map((page) => page.chapter)));

/**
 * Notebook-style shopkeeper manual: contents spine + turnable pages.
 */
export const ManualPageView = () => {
  const [pageIndex, setPageIndex] = useState(0);
  const page: ManualPage = MANUAL_PAGES[pageIndex];
  const isFirst = pageIndex === 0;
  const isLast = pageIndex === MANUAL_PAGES.length - 1;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight" && !isLast) {
        setPageIndex((current) => current + 1);
      }
      if (event.key === "ArrowLeft" && !isFirst) {
        setPageIndex((current) => current - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isFirst, isLast]);

  return (
    <section className="mx-auto max-w-5xl">
      <p className="text-[11px] tracking-[0.2em] text-[var(--muted)] uppercase">Shop notebook</p>
      <h2 className="mt-2 text-3xl">Manual</h2>
      <p className="mt-2 max-w-2xl font-sans text-sm text-[var(--muted)]">
        Page-by-page guide for running the counter. Use the contents list or flip pages. Arrow keys work too.
      </p>

      <div className="mt-6 grid gap-4 lg:grid-cols-[15rem_minmax(0,1fr)]">
        <aside className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-3 shadow-[var(--shadow)]">
          <p className="px-2 text-[11px] tracking-[0.16em] text-[var(--muted)] uppercase">Contents</p>
          <nav className="mt-2 max-h-[70vh] space-y-3 overflow-y-auto font-sans text-sm">
            {chapters.map((chapter) => (
              <div key={chapter}>
                <p className="px-2 text-xs font-medium text-[var(--accent)]">{chapter}</p>
                <ul className="mt-1">
                  {MANUAL_PAGES.filter((entry) => entry.chapter === chapter).map((entry) => {
                    const index = MANUAL_PAGES.findIndex((row) => row.id === entry.id);
                    const active = index === pageIndex;
                    return (
                      <li key={entry.id}>
                        <button
                          type="button"
                          onClick={() => setPageIndex(index)}
                          className={[
                            "w-full rounded-md px-2 py-1.5 text-left",
                            active
                              ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                              : "text-[var(--ink)] hover:bg-[var(--paper)]",
                          ].join(" ")}
                        >
                          <span className="mr-1.5 text-[10px] text-[var(--muted)]">{index + 1}.</span>
                          {entry.title}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>
        </aside>

        <article className="relative overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--panel)] shadow-[var(--shadow)]">
          <div
            className="pointer-events-none absolute inset-y-0 left-0 w-3 border-r border-[var(--line)]"
            style={{
              background:
                "repeating-linear-gradient(180deg, transparent, transparent 10px, color-mix(in srgb, var(--line) 55%, transparent) 10px, color-mix(in srgb, var(--line) 55%, transparent) 11px)",
            }}
            aria-hidden
          />
          <div className="border-b border-[var(--line)] px-8 py-4 sm:pl-10">
            <p className="font-sans text-xs text-[var(--muted)]">
              {page.chapter} · Page {pageIndex + 1} of {MANUAL_PAGES.length}
            </p>
            <h3 className="mt-1 text-2xl">{page.title}</h3>
          </div>

          <div className="min-h-[28rem] space-y-4 px-8 py-6 font-sans text-sm leading-relaxed sm:pl-10">
            {page.body.map((paragraph) => (
              <p key={paragraph} className="text-[var(--ink)]">
                {paragraph}
              </p>
            ))}

            {page.fields?.length ? (
              <div className="rounded-lg border border-[var(--line)] bg-[var(--paper)] p-4">
                <p className="text-[11px] tracking-[0.14em] text-[var(--muted)] uppercase">Fields on this page</p>
                <dl className="mt-3 space-y-3">
                  {page.fields.map((field) => (
                    <div key={field.name}>
                      <dt className="font-medium text-[var(--accent)]">{field.name}</dt>
                      <dd className="mt-0.5 text-[var(--muted)]">{field.meaning}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ) : null}

            {page.tip ? (
              <p className="rounded-md border border-[var(--warn-line)] bg-[var(--warn-bg)] px-3 py-2 text-[var(--warn-ink)]">
                <span className="font-medium">Tip — </span>
                {page.tip}
              </p>
            ) : null}
          </div>

          <div className="flex items-center justify-between gap-3 border-t border-[var(--line)] px-8 py-4 sm:pl-10">
            <button
              type="button"
              disabled={isFirst}
              className="h-10 rounded-md border border-[var(--line)] px-4 text-sm disabled:opacity-40"
              onClick={() => setPageIndex((current) => current - 1)}
            >
              ← Previous
            </button>
            <span className="hidden text-xs text-[var(--muted)] sm:inline">Flip with ← → keys</span>
            <button
              type="button"
              disabled={isLast}
              className="h-10 rounded-md bg-[var(--accent)] px-4 text-sm text-[var(--on-accent)] disabled:opacity-40"
              onClick={() => setPageIndex((current) => current + 1)}
            >
              Next →
            </button>
          </div>
        </article>
      </div>
    </section>
  );
};
