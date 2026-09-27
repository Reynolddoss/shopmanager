/**
 * Catalog photo picker: preview, upload, and clear.
 * Used on new-product review and the product detail overview.
 */

import { useEffect, useState } from "react";
import { useToast } from "../hooks/useToast.ts";
import { apiClient } from "../services/api.ts";

type ProductImageFieldProps = {
  /** When set, uploads go straight to the API. When omitted, only local preview is kept. */
  productId?: number | null;
  imageUrl?: string | null;
  /** Local file chosen before the product exists (create wizard). */
  pendingFile?: File | null;
  onPendingFile?: (file: File | null) => void;
  onUploaded?: (imageUrl: string | null) => void;
  compact?: boolean;
};

export const ProductImageField = ({
  productId,
  imageUrl,
  pendingFile = null,
  onPendingFile,
  onUploaded,
  compact = false,
}: ProductImageFieldProps) => {
  const { push } = useToast();
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);

  useEffect(() => {
    if (!pendingFile) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(pendingFile);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [pendingFile]);

  const shown = preview || imageUrl || null;

  const pick = (file: File | null) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      push("error", "Not a picture", "Choose a JPG, PNG, WEBP, or GIF file.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      push("error", "Too large", "Keep the picture under 5 MB.");
      return;
    }
    if (productId) {
      setBusy(true);
      void apiClient
        .uploadProductImage(productId, file)
        .then((row) => {
          onUploaded?.(row.image_url ?? null);
          push("success", "Photo saved", "Product picture updated.");
        })
        .catch((err: unknown) =>
          push("error", "Upload failed", err instanceof Error ? err.message : "Request failed."),
        )
        .finally(() => setBusy(false));
      return;
    }
    onPendingFile?.(file);
  };

  const clear = () => {
    if (productId && imageUrl) {
      setBusy(true);
      void apiClient
        .clearProductImage(productId)
        .then(() => {
          onUploaded?.(null);
          push("success", "Photo removed", "Catalog picture cleared.");
        })
        .catch((err: unknown) =>
          push("error", "Could not remove", err instanceof Error ? err.message : "Request failed."),
        )
        .finally(() => setBusy(false));
      return;
    }
    onPendingFile?.(null);
  };

  return (
    <div className={compact ? "font-sans text-sm" : "rounded-xl border border-[var(--line)] bg-[var(--panel)] p-4 font-sans text-sm"}>
      {!compact ? (
        <p className="text-xs tracking-[0.12em] text-[var(--muted)] uppercase">Product photo</p>
      ) : null}
      <div className={["flex flex-wrap items-start gap-3", compact ? "" : "mt-3"].join(" ")}>
        <div
          className={[
            "flex shrink-0 items-center justify-center overflow-hidden border border-[var(--line)] bg-[var(--paper)]",
            compact ? "h-16 w-16 rounded-md" : "h-28 w-28 rounded-lg",
          ].join(" ")}
        >
          {shown ? (
            <img src={shown} alt="" className="h-full w-full object-cover" />
          ) : (
            <span className="px-2 text-center text-[11px] text-[var(--muted)]">No photo</span>
          )}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <label className="inline-flex cursor-pointer">
            <span className="rounded-md border border-[var(--line)] bg-[var(--btn-face)] px-3 py-2 text-sm font-semibold">
              {busy ? "Working…" : shown ? "Change photo" : "Add photo"}
            </span>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              className="sr-only"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0] ?? null;
                pick(file);
                e.target.value = "";
              }}
            />
          </label>
          {shown ? (
            <button type="button" className="w-fit shadow-none" disabled={busy} onClick={clear}>
              Remove
            </button>
          ) : null}
          <p className="text-xs text-[var(--muted)]">JPG, PNG, WEBP, or GIF · up to 5 MB</p>
        </div>
      </div>
    </div>
  );
};
