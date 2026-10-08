import { Link } from "react-router-dom";
import type { ReactNode } from "react";

export function BrandMark(): JSX.Element {
  return (
    <Link to="/" className="flex items-center gap-3 shrink-0" aria-label="AquaAgent overview">
      <span className="w-6 h-6 border-2 border-white bg-panel flex items-center justify-center font-mono-cad font-bold text-[10px]">AQ</span>
      <span className="font-heading font-extrabold text-lg tracking-tight">AquaAgent</span>
    </Link>
  );
}

/** Shared fixed header: brand on the left, page-specific `center` and `right` slots. */
export function Header({ tag, center, right }: { tag?: string; center?: ReactNode; right?: ReactNode }): JSX.Element {
  return (
    <header className="fixed top-0 inset-x-0 z-50 bg-blueprint/95 backdrop-blur border-b border-white/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <BrandMark />
          {tag && <span className="max-sm:hidden font-mono-cad text-[10px] text-paler border-l border-white/40 pl-3 whitespace-nowrap">{tag}</span>}
        </div>
        {center && <div className="hidden md:flex flex-1 justify-center min-w-0">{center}</div>}
        <div className="flex items-center gap-2 shrink-0">{right}</div>
      </div>
    </header>
  );
}
