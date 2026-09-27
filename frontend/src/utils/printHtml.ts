/**
 * Print a server-rendered HTML document (e.g. an invoice) without a popup window.
 *
 * Popups are unreliable inside the desktop webview, so the document is loaded
 * into one reusable, invisible iframe. The invoice HTML calls window.print()
 * on load, which prints just the iframe content.
 */

const FRAME_ID = "mm-print-frame";

const ensurePrintFrame = (): HTMLIFrameElement => {
  const existing = document.getElementById(FRAME_ID);
  if (existing instanceof HTMLIFrameElement) return existing;
  const frame = document.createElement("iframe");
  frame.id = FRAME_ID;
  frame.title = "Print preview";
  frame.setAttribute("aria-hidden", "true");
  // Not display:none: some engines skip loading/printing hidden frames.
  Object.assign(frame.style, { position: "fixed", right: "0", bottom: "0", width: "0", height: "0", border: "0", opacity: "0" });
  document.body.appendChild(frame);
  return frame;
};

export const printHtmlDocument = (html: string): void => {
  ensurePrintFrame().srcdoc = html;
};
