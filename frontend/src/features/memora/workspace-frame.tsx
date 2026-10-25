"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  AudioLines,
  LayoutList,
  Settings,
  ShieldCheck,
  ChevronRight,
  FileText,
} from "lucide-react";
import { useMemoraText } from "./i18n";
import s from "./workspace-frame.module.css";
export function WorkspaceFrame({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const tr = useMemoraText();
  const workspace =
    path === "/" || path.startsWith("/reunions/") || path === "/parametres";
  if (!workspace) return <div className={s.theme}>{children}</div>;
  return (
    <div className={`${s.theme} ${s.frame}`}>
      <aside className={s.rail} aria-label={tr("Navigation de l’espace")}>
        <Link href="/" className={s.brand}>
          <span className={s.mark}>
            <AudioLines size={23} />
          </span>
          <span>
            Memora<span className={s.dot}>.</span>
          </span>
        </Link>
        <div className={s.workspace}>
          <span className={s.workspaceIcon}>M</span>
          <span>
            <strong>{tr("Mon espace")}</strong>
            <small>{tr("Réunions & connaissance")}</small>
          </span>
          <ChevronRight size={14} />
        </div>
        <div className={s.label}>{tr("BIBLIOTHÈQUE")}</div>
        <nav className={s.links}>
          <Link
            href="/"
            className={path !== "/parametres" ? s.active : ""}
            aria-current={path !== "/parametres" ? "page" : undefined}
          >
            <LayoutList size={19} />
            {tr("Mes réunions")}
          </Link>
          <Link
            href="/parametres"
            className={path === "/parametres" ? s.active : ""}
            aria-current={path === "/parametres" ? "page" : undefined}
          >
            <Settings size={19} />
            {tr("Paramètres")}
          </Link>
        </nav>
        <div className={s.memoryCard}>
          <div className={s.orbit}>
            <FileText size={25} />
            <span />
            <span />
          </div>
          <strong>{tr("Des échanges aux idées claires.")}</strong>
          <p>
            {tr(
              "Vos rapports, vos décisions et leurs sources réunis dans un seul espace.",
            )}
          </p>
        </div>
        <div className={s.local}>
          <ShieldCheck size={17} />
          <span>
            {tr("IA locale")}
            <small>{tr("Votre mémoire vous appartient")}</small>
          </span>
          <i />
        </div>
      </aside>
      <div className={s.content}>{children}</div>
    </div>
  );
}
