"use client";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { useI18n } from "@/lib/i18n/use-i18n";
import styles from "./modal.module.css";

/** Dialogue natif : focus contenu, arrière-plan inerte, fermeture Échap et restitution du focus. */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  const { t } = useI18n();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (!open) {
      if (dialog.open) dialog.close();
      return;
    }
    const previousOverflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = "hidden";
    if (!dialog.open) dialog.showModal();
    dialog
      .querySelector<HTMLInputElement>(
        'input:not([type="hidden"]):not([readonly]):not([disabled])',
      )
      ?.focus();
    return () => {
      if (dialog.open) dialog.close();
      document.documentElement.style.overflow = previousOverflow;
    };
  }, [open]);
  return (
    <dialog
      ref={ref}
      className={styles.dialog}
      aria-labelledby={id}
      aria-describedby={description ? `${id}-description` : undefined}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClose={() => {
        if (open) onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          const rect = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < rect.left ||
            event.clientX > rect.right ||
            event.clientY < rect.top ||
            event.clientY > rect.bottom
          )
            onClose();
        }
      }}
    >
      {open && (
        <>
          <header className={styles.header}>
            <div>
              <h2 id={id}>{title}</h2>
              {description && <p id={`${id}-description`}>{description}</p>}
            </div>
            <button
              type="button"
              className={styles.close}
              aria-label={t("Fermer")}
              onClick={onClose}
            >
              <X size={18} />
            </button>
          </header>
          <div className={styles.body}>{children}</div>
        </>
      )}
    </dialog>
  );
}
