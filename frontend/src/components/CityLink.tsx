// Link to the /city concept demo with a "water spreading" reveal (View Transitions API).
// Preloads the lazy City chunk on hover/focus so the transition never shows a loading state.
// Falls back to plain navigation (City's own CSS entrance) when the API is missing or motion is reduced.
import type { MouseEvent, ReactNode } from "react";
import { flushSync } from "react-dom";
import { useNavigate } from "react-router-dom";

export const loadCity = () => import("../pages/City");

type ViewTransitionDocument = Document & {
  startViewTransition?: (update: () => void) => { finished: Promise<void> };
};

function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

export function CityLink({ className, children }: { className?: string; children: ReactNode }): JSX.Element {
  const navigate = useNavigate();

  async function onClick(e: MouseEvent<HTMLAnchorElement>): Promise<void> {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return; // keep new-tab behaviour
    e.preventDefault();
    const doc = document as ViewTransitionDocument;
    await loadCity(); // chunk ready before the snapshot is taken
    if (!doc.startViewTransition || prefersReducedMotion()) {
      navigate("/city");
      return;
    }
    const root = document.documentElement;
    root.style.setProperty("--reveal-x", `${e.clientX}px`);
    root.style.setProperty("--reveal-y", `${e.clientY}px`);
    root.dataset.transition = "city";
    const t = doc.startViewTransition(() => {
      flushSync(() => navigate("/city"));
      window.scrollTo(0, 0);
    });
    t.finished.finally(() => {
      delete root.dataset.transition;
    });
  }

  return (
    <a href="/city" className={className} onClick={onClick} onMouseEnter={loadCity} onFocus={loadCity}>
      {children}
    </a>
  );
}
