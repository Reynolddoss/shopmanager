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
  // A real A4 frame. A zero-size frame lays the bill out in no space, so the
  // printed page is not A4. Opacity hides it; display:none would skip printing.
  Object.assign(frame.style, {
    position: "fixed",
    left: "0",
    top: "0",
    width: "210mm",
    height: "297mm",
    border: "0",
    opacity: "0",
    pointerEvents: "none",
    zIndex: "-1",
  });
  document.body.appendChild(frame);
  return frame;
};

export const printHtmlDocument = (html: string): void => {
  ensurePrintFrame().srcdoc = html;
};
