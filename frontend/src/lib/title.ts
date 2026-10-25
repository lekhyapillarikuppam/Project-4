import { useEffect } from "react";

/** Each route names itself in the browser tab and to screen readers (WCAG 2.4.2). */
export function useDocumentTitle(title: string | null | undefined) {
  useEffect(() => {
    document.title = title ? `${title} · Tripwise` : "Tripwise";
  }, [title]);
}
