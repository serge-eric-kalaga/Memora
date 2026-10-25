"use client";
import { useId } from "react";
import { useMemoraText } from "./i18n";
import s from "./memora.module.css";
export function AudioLanguage({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const tr = useMemoraText();
  const fieldId = useId();
  return (
    <div className={s.field}>
      <label htmlFor={fieldId} className={s.fieldLabel}>
        {tr("Langue de l’audio")}
      </label>
      <select
        id={fieldId}
        aria-describedby={`${fieldId}-help`}
        className={s.select}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="auto">{tr("Automatique · français / anglais")}</option>
        <option value="fr">{tr("Français")}</option>
        <option value="en">English</option>
      </select>
      <small id={`${fieldId}-help`} className={`${s.muted} ${s.languageHelp}`}>
        {tr(
          "Choisissez Français ou English pour un audio monolingue, Automatique pour une alternance de langues.",
        )}
      </small>
    </div>
  );
}
