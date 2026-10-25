"use client";
import { useState, type ComponentProps } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useI18n } from "@/lib/i18n/use-i18n";
import { Field } from "./field";

/** Champ de mot de passe commun, compatible React Hook Form et navigation clavier. */
export function PasswordField(
  props: Omit<ComponentProps<typeof Field>, "type">,
) {
  const [visible, setVisible] = useState(false);
  const { t } = useI18n();
  return (
    <div className="password-field">
      <Field {...props} type={visible ? "text" : "password"} />
      <button
        type="button"
        className="password-toggle"
        onClick={() => setVisible((current) => !current)}
        aria-label={t(
          visible ? "Masquer le mot de passe" : "Afficher le mot de passe",
        )}
        aria-pressed={visible}
      >
        {visible ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </div>
  );
}
