"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n/use-i18n";
import { Modal } from "./modal";
import styles from "./confirmation.module.css";
type Options = {
  title: string;
  message: string;
  confirmLabel: string;
  destructive?: boolean;
};
/** Awaitable confirmation scoped to the mounted view; closing/unmounting cancels. */
export function useConfirmation() {
  const [options, setOptions] = useState<Options | null>(null);
  const resolver = useRef<((answer: boolean) => void) | null>(null);
  const finish = useCallback((answer: boolean) => {
    const resolve = resolver.current;
    resolver.current = null;
    setOptions(null);
    resolve?.(answer);
  }, []);
  useEffect(
    () => () => {
      resolver.current?.(false);
      resolver.current = null;
    },
    [],
  );
  const confirm = useCallback((next: Options) => {
    if (resolver.current) return Promise.resolve(false);
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve;
      setOptions(next);
    });
  }, []);
  return {
    confirm,
    confirmation: <Confirmation options={options} finish={finish} />,
  };
}
function Confirmation({
  options,
  finish,
}: {
  options: Options | null;
  finish: (answer: boolean) => void;
}) {
  const { language } = useI18n();
  const cancel = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (options) cancel.current?.focus();
  }, [options]);
  return (
    <Modal
      open={!!options}
      onClose={() => finish(false)}
      title={options?.title || ""}
      description={options?.message}
    >
      <div className={styles.actions}>
        <button
          ref={cancel}
          type="button"
          className={styles.cancel}
          onClick={() => finish(false)}
        >
          {language === "en" ? "Cancel" : "Annuler"}
        </button>
        <button
          type="button"
          className={`${styles.confirm} ${options?.destructive ? styles.destructive : ""}`}
          onClick={() => finish(true)}
        >
          {options?.confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
