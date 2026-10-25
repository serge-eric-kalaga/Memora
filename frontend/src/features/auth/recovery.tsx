"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircle, ShieldCheck } from "lucide-react";
import { Field } from "@/components/ui/field";
import { PasswordField } from "@/components/ui/password-field";
import { useI18n } from "@/lib/i18n/use-i18n";
import { authApi } from "./api";
import { useCredentialChange } from "./hooks";
import {
  forgotPasswordSchema,
  passwordFieldsSchema,
  type ForgotPasswordInput,
  type PasswordFieldsInput,
  type ResetPasswordInput,
} from "./schemas";

/** Parcours de récupération commun aux projets démarrés avec le template. */
export function Recovery({ mode }: { mode: "forgot" | "reset" }) {
  const { t } = useI18n();
  return (
    <main className="auth-layout page-shell">
      <aside className="auth-story">
        <span className="eyebrow">
          {t("RÉCUPÉRATION · MODULE DU TEMPLATE")}
        </span>
        <h1>{t("Retrouver l’accès à votre compte.")}</h1>
        <p>
          {t(
            "Un parcours de récupération par e-mail, prêt à adapter aux besoins de votre projet.",
          )}
        </p>
        <div className="story-note">
          <ShieldCheck size={21} />
          <span>{t("Un lien temporaire, utilisable une seule fois.")}</span>
        </div>
      </aside>
      <section className="auth-card">
        <h2>
          {t(
            mode === "forgot"
              ? "Mot de passe oublié"
              : "Réinitialiser le mot de passe",
          )}
        </h2>
        {mode === "forgot" ? <ForgotForm /> : <ResetToken />}
      </section>
    </main>
  );
}

function BackToLogin() {
  const { t } = useI18n();
  return (
    <p className="auth-switch">
      <Link href="/connexion">{t("Retour à la connexion")}</Link>
    </p>
  );
}

function ForgotForm() {
  const { t, language } = useI18n();
  const form = useForm<ForgotPasswordInput>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });
  const mutation = useMutation({
    mutationFn: (body: ForgotPasswordInput) =>
      authApi.forgotPassword(body, language),
    gcTime: 0,
  });
  return (
    <>
      <p className="muted">
        {t("Saisissez l’adresse e-mail associée à votre compte.")}
      </p>
      {mutation.isSuccess ? (
        <p role="status" className="notice notice-success recovery-notice">
          {t(
            "Si un compte correspond à cette adresse, vous recevrez un lien de réinitialisation.",
          )}
        </p>
      ) : null}
      <form
        className="form-stack"
        noValidate
        onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
      >
        <Field
          id="forgot-email"
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
        />
        {mutation.error ? (
          <p className="notice notice-error" role="alert">
            {t(mutation.error.message)}
          </p>
        ) : null}
        <button
          type="submit"
          className="button button-primary button-full"
          disabled={mutation.isPending}
        >
          {mutation.isPending ? (
            <LoaderCircle size={16} className="spin" />
          ) : null}
          {t("Envoyer un lien de réinitialisation")}
        </button>
      </form>
      <BackToLogin />
    </>
  );
}

function ResetToken() {
  const { t } = useI18n();
  const [token, setToken] = useState<string | null | undefined>(undefined);
  const captured = useRef(false);
  const [generation, setGeneration] = useState(0);
  useEffect(() => {
    const capture = () => {
      const parameters = new URLSearchParams(window.location.hash.slice(1));
      if (captured.current && !parameters.has("token")) return;
      captured.current = true;
      const candidate = parameters.get("token");
      // Les fragments ordinaires (ex. lien d’évitement) ne remplacent pas un jeton déjà lu.
      window.history.replaceState(
        window.history.state,
        "",
        window.location.pathname,
      );
      setToken(
        candidate && /^[A-Za-z0-9_-]{43}$/.test(candidate) ? candidate : null,
      );
      setGeneration((current) => current + 1);
    };
    capture();
    window.addEventListener("hashchange", capture);
    return () => window.removeEventListener("hashchange", capture);
  }, []);
  if (token === undefined)
    return <p role="status">{t("Chargement du lien…")}</p>;
  if (!token)
    return (
      <>
        <p className="notice notice-error recovery-notice" role="alert">
          {t("Le lien est invalide ou a expiré. Demandez un nouveau lien.")}
        </p>
        <p className="auth-switch">
          <Link href="/mot-de-passe-oublie">
            {t("Demander un nouveau lien")}
          </Link>
        </p>
        <BackToLogin />
      </>
    );
  return <ResetForm key={generation} token={token} />;
}

function ResetForm({ token }: { token: string }) {
  const { t, language } = useI18n();
  const [complete, setComplete] = useState(false);
  const form = useForm<PasswordFieldsInput>({
    resolver: zodResolver(passwordFieldsSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  });
  const mutation = useCredentialChange((body: ResetPasswordInput) =>
    authApi.resetPassword(body, language),
  );
  if (complete)
    return (
      <>
        <p role="status" className="notice notice-success recovery-notice">
          {t(
            "Votre mot de passe a été réinitialisé. Connectez-vous avec le nouveau mot de passe.",
          )}
        </p>
        <BackToLogin />
      </>
    );
  return (
    <>
      <p className="muted">
        {t(
          "Choisissez un nouveau mot de passe. Toutes les anciennes sessions seront invalidées.",
        )}
      </p>
      <form
        className="form-stack"
        noValidate
        onSubmit={form.handleSubmit((values) =>
          mutation.mutate(
            { ...values, token },
            {
              onSuccess: () => {
                form.reset();
                setComplete(true);
                mutation.reset();
              },
            },
          ),
        )}
      >
        <PasswordField
          id="reset-new-password"
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
          id="reset-confirm-password"
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
          type="submit"
          className="button button-primary button-full"
          disabled={mutation.isPending}
        >
          {mutation.isPending ? (
            <LoaderCircle size={16} className="spin" />
          ) : null}
          {t("Réinitialiser le mot de passe")}
        </button>
      </form>
      <p className="auth-switch">
        <Link href="/mot-de-passe-oublie">{t("Demander un nouveau lien")}</Link>
      </p>
      <BackToLogin />
    </>
  );
}
