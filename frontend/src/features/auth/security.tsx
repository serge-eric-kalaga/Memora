"use client";

import { useState } from "react";
import { Modal } from "@/components/ui/modal";
import { Mail, LockKeyhole } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircle } from "lucide-react";
import { Field } from "@/components/ui/field";
import { PasswordField } from "@/components/ui/password-field";
import { useI18n } from "@/lib/i18n/use-i18n";
import { authApi } from "./api";
import { useCredentialChange } from "./hooks";
import {
  changePasswordSchema,
  changeEmailSchema,
  type ChangePasswordInput,
  type ChangeEmailInput,
} from "./schemas";

export type CredentialNotice = "email-changed" | "password-changed";
type OnCredentialsChanged = (notice: CredentialNotice) => void;
export function AccountSecurity({
  email,
  onCredentialsChanged,
}: {
  email: string | null;
  onCredentialsChanged: OnCredentialsChanged;
}) {
  const { t } = useI18n();
  const [active, setActive] = useState<"email" | "password" | null>(null);
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>{t("Sécurité du compte")}</h2>
          <p className="muted">
            {t("Gérez vos identifiants et vos options de récupération.")}
          </p>
        </div>
      </div>
      <div className="account-action-row">
        <span className="account-action-icon">
          <Mail size={18} aria-hidden="true" />
        </span>
        <div>
          <h3>{t("Adresse de récupération")}</h3>
          <p>{email || t("Aucune adresse e-mail")}</p>
        </div>
        <button
          type="button"
          className="button button-outline"
          onClick={() => setActive("email")}
        >
          {t("Modifier")}
        </button>
      </div>
      <div className="account-action-row">
        <span className="account-action-icon">
          <LockKeyhole size={18} aria-hidden="true" />
        </span>
        <div>
          <h3>{t("Mot de passe")}</h3>
          <p>{t("Protégez l’accès à votre compte.")}</p>
        </div>
        <button
          type="button"
          className="button button-outline"
          onClick={() => setActive("password")}
        >
          {t("Modifier")}
        </button>
      </div>
      <Modal
        open={active === "email"}
        onClose={() => setActive(null)}
        title={t("Adresse de récupération")}
        description={t(
          "Associez une adresse e-mail pour pouvoir récupérer votre compte.",
        )}
      >
        <EmailForm email={email} onCredentialsChanged={onCredentialsChanged} />
      </Modal>
      <Modal
        open={active === "password"}
        onClose={() => setActive(null)}
        title={t("Modifier le mot de passe")}
        description={t(
          "Confirmez votre mot de passe actuel. Vous devrez ensuite vous reconnecter.",
        )}
      >
        <PasswordForm onCredentialsChanged={onCredentialsChanged} />
      </Modal>
    </section>
  );
}

function EmailForm({
  email,
  onCredentialsChanged,
}: {
  email: string | null;
  onCredentialsChanged: OnCredentialsChanged;
}) {
  const { t, language } = useI18n();
  const form = useForm<ChangeEmailInput>({
    resolver: zodResolver(changeEmailSchema),
    defaultValues: { email: email || "", current_password: "" },
  });
  const mutation = useCredentialChange(
    (body: ChangeEmailInput) => authApi.changeEmail(body, language),
    () => onCredentialsChanged("email-changed"),
  );
  return (
    <form
      className="form-stack"
      method="post"
      noValidate
      onSubmit={form.handleSubmit((values) =>
        mutation.mutate(values, {
          onSuccess: () => {
            form.reset();
          },
        }),
      )}
    >
      <Field
        id="recovery-email"
        label={t("Adresse e-mail")}
        type="email"
        autoComplete="email"
        maxLength={254}
        {...form.register("email")}
        error={
          form.formState.errors.email?.message
            ? t(form.formState.errors.email.message)
            : undefined
        }
        hint={
          email
            ? t("Votre adresse de récupération actuelle.")
            : t(
                "Aucune adresse de récupération n’est encore associée à ce compte.",
              )
        }
      />
      <PasswordField
        id="email-current-password"
        label={t("Mot de passe actuel")}
        autoComplete="current-password"
        maxLength={128}
        {...form.register("current_password")}
        error={
          form.formState.errors.current_password?.message
            ? t(form.formState.errors.current_password.message)
            : undefined
        }
      />
      {mutation.error ? (
        <p className="notice notice-error" role="alert">
          {t(mutation.error.message)}
        </p>
      ) : null}
      <button
        className="button button-outline"
        disabled={mutation.isPending}
        type="submit"
      >
        {mutation.isPending ? (
          <LoaderCircle size={16} className="spin" />
        ) : null}
        {t("Enregistrer l’adresse e-mail")}
      </button>
    </form>
  );
}

function PasswordForm({
  onCredentialsChanged,
}: {
  onCredentialsChanged: OnCredentialsChanged;
}) {
  const { t, language } = useI18n();
  const form = useForm<ChangePasswordInput>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  });
  const mutation = useCredentialChange(
    (body: ChangePasswordInput) => authApi.changePassword(body, language),
    () => onCredentialsChanged("password-changed"),
  );
  return (
    <form
      className="form-stack"
      method="post"
      noValidate
      onSubmit={form.handleSubmit((values) =>
        mutation.mutate(values, {
          onSuccess: () => {
            form.reset();
          },
        }),
      )}
    >
      <PasswordField
        id="change-current-password"
        label={t("Mot de passe actuel")}
        autoComplete="current-password"
        maxLength={128}
        {...form.register("current_password")}
        error={
          form.formState.errors.current_password?.message
            ? t(form.formState.errors.current_password.message)
            : undefined
        }
      />
      <PasswordField
        id="change-new-password"
        label={t("Nouveau mot de passe")}
        autoComplete="new-password"
        maxLength={128}
        {...form.register("new_password")}
        error={
          form.formState.errors.new_password?.message
            ? t(form.formState.errors.new_password.message)
            : undefined
        }
        hint={t(
          "8 à 128 caractères. Choisissez un mot de passe différent de l’actuel.",
        )}
      />
      <PasswordField
        id="change-confirm-password"
        label={t("Confirmer le nouveau mot de passe")}
        autoComplete="new-password"
        maxLength={128}
        {...form.register("confirm_password")}
        error={
          form.formState.errors.confirm_password?.message
            ? t(form.formState.errors.confirm_password.message)
            : undefined
        }
      />
      {mutation.error ? (
        <p className="notice notice-error" role="alert">
          {t(mutation.error.message)}
        </p>
      ) : null}
      <button
        className="button button-primary"
        disabled={mutation.isPending}
        type="submit"
      >
        {mutation.isPending ? (
          <LoaderCircle size={16} className="spin" />
        ) : null}
        {t("Enregistrer le nouveau mot de passe")}
      </button>
    </form>
  );
}
