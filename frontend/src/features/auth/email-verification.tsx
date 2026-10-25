"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircle, MailCheck } from "lucide-react";
import { Field } from "@/components/ui/field";
import { useI18n } from "@/lib/i18n/use-i18n";
import { authApi } from "./api";
import { useCredentialChange } from "./hooks";
import { forgotPasswordSchema, type ForgotPasswordInput } from "./schemas";

/** Formulaire partagé entre l’inscription en attente et la page de renvoi. */
export function ResendVerification({
  initialEmail = "",
}: {
  initialEmail?: string;
}) {
  const { t, language } = useI18n();
  const form = useForm<ForgotPasswordInput>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: initialEmail },
  });
  const mutation = useMutation({
    mutationFn: (values: ForgotPasswordInput) =>
      authApi.resendVerification(values.email, language),
    gcTime: 0,
  });
  return (
    <>
      <p className="muted">
        {t(
          "Consultez aussi vos courriers indésirables. Vous pouvez demander un nouveau lien ci-dessous.",
        )}
      </p>
      <form
        className="form-stack"
        noValidate
        onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
      >
        <Field
          id="confirmation-email"
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
        {mutation.isSuccess ? (
          <p role="status" className="notice notice-success">
            {t(
              "Si une confirmation est nécessaire, vous recevrez un nouveau lien par e-mail.",
            )}
          </p>
        ) : null}
        {mutation.error ? (
          <p role="alert" className="notice notice-error">
            {t(mutation.error.message)}
          </p>
        ) : null}
        <button
          type="submit"
          className="button button-primary button-full"
          disabled={mutation.isPending}
        >
          {mutation.isPending ? (
            <LoaderCircle className="spin" size={16} />
          ) : null}
          {t("Renvoyer le lien de confirmation")}
        </button>
      </form>
    </>
  );
}

/** Le fragment reste en mémoire ; un clic explicite évite la consommation par les scanners d’e-mails. */
export function EmailVerification() {
  const { t } = useI18n();
  const [link, setLink] = useState<{
    token: string | null;
    generation: number;
  } | null>(null);
  const captured = useRef(false);
  useEffect(() => {
    function capture() {
      const params = new URLSearchParams(window.location.hash.slice(1));
      if (captured.current && !params.has("token")) return;
      captured.current = true;
      const value = params.get("token");
      window.history.replaceState(
        window.history.state,
        "",
        window.location.pathname,
      );
      setLink((previous) => ({
        token:
          value && /^[A-Za-z0-9_-]{43}$/.test(value)
            ? value
            : params.has("token")
              ? ""
              : null,
        generation: (previous?.generation || 0) + 1,
      }));
    }
    capture();
    window.addEventListener("hashchange", capture);
    return () => window.removeEventListener("hashchange", capture);
  }, []);
  return (
    <main className="auth-layout page-shell">
      <aside className="auth-story">
        <span className="eyebrow">{t("E-MAIL · MODULE DU TEMPLATE")}</span>
        <h1>{t("Confirmer votre adresse e-mail.")}</h1>
        <p>
          {t(
            "Une vérification optionnelle, prête à intégrer aux inscriptions de votre projet.",
          )}
        </p>
        <div className="story-note">
          <MailCheck size={21} />
          <span>{t("Un lien temporaire, utilisable une seule fois.")}</span>
        </div>
      </aside>
      <section className="auth-card">
        <h2>{t("Confirmer l’adresse e-mail")}</h2>
        {link === null ? (
          <p role="status">{t("Chargement du lien…")}</p>
        ) : link.token ? (
          <ConfirmToken key={link.generation} token={link.token} />
        ) : (
          <>
            {link.token === "" ? (
              <p role="alert" className="notice notice-error">
                {t(
                  "Le lien de confirmation est invalide ou a expiré. Demandez un nouveau lien.",
                )}
              </p>
            ) : null}
            <ResendVerification />
          </>
        )}
        <p className="auth-switch">
          <Link href="/connexion">{t("Retour à la connexion")}</Link>
        </p>
      </section>
    </main>
  );
}

function ConfirmToken({ token }: { token: string }) {
  const { t } = useI18n();
  const mutation = useCredentialChange(authApi.verifyEmail);
  if (mutation.isSuccess)
    return (
      <p role="status" className="notice notice-success recovery-notice">
        {t("Adresse e-mail confirmée. Vous pouvez maintenant vous connecter.")}
      </p>
    );
  return (
    <>
      <p className="muted">
        {t("Cliquez pour confirmer l’adresse associée à votre compte.")}
      </p>
      {mutation.error ? (
        <p role="alert" className="notice notice-error">
          {t(mutation.error.message)}
        </p>
      ) : null}
      <button
        type="button"
        className="button button-primary button-full"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate(token)}
      >
        {mutation.isPending ? (
          <LoaderCircle className="spin" size={16} />
        ) : null}
        {t("Confirmer mon adresse")}
      </button>
      {mutation.isError ? <ResendVerification /> : null}
    </>
  );
}
