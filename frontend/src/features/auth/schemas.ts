import { z } from "zod";

const username = z
  .string()
  .trim()
  .min(3, "Au moins 3 caractères.")
  .max(64, "64 caractères maximum.")
  .regex(
    /^[\p{L}\p{N}_.-]+$/u,
    "Utilisez des lettres, chiffres, points, tirets ou underscores.",
  );
export const loginSchema = z.object({
  username,
  password: z
    .string()
    .min(1, "Saisissez votre mot de passe.")
    .max(128, "128 caractères maximum."),
});
export const registerSchema = z.object({
  username,
  email: z
    .union([
      z.email("Adresse e-mail invalide.").max(254, "254 caractères maximum."),
      z.literal(""),
    ])
    .optional(),
  telephone: z.string().trim().max(32, "32 caractères maximum."),
  password: z
    .string()
    .min(8, "Au moins 8 caractères.")
    .max(128, "128 caractères maximum."),
});
export const profileSchema = z.object({
  telephone: z.string().trim().max(32, "32 caractères maximum."),
});
export type LoginInput = z.infer<typeof loginSchema>;
export type RegisterInput = z.infer<typeof registerSchema>;
export type ProfileInput = z.infer<typeof profileSchema>;

const email = z
  .email("Adresse e-mail invalide.")
  .max(254, "254 caractères maximum.");
export const forgotPasswordSchema = z.object({ email });
const newPassword = z
  .string()
  .min(8, "Au moins 8 caractères.")
  .max(128, "128 caractères maximum.");
export const passwordFieldsSchema = z
  .object({
    new_password: newPassword,
    confirm_password: z.string().min(1, "Confirmez le nouveau mot de passe."),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    path: ["confirm_password"],
    message: "Les mots de passe ne correspondent pas.",
  });
export const changePasswordSchema = passwordFieldsSchema.safeExtend({
  current_password: z
    .string()
    .min(1, "Saisissez votre mot de passe.")
    .max(128, "128 caractères maximum."),
});
export const resetPasswordSchema = passwordFieldsSchema.safeExtend({
  token: z
    .string()
    .regex(
      /^[A-Za-z0-9_-]{43}$/,
      "Le lien est invalide ou a expiré. Demandez un nouveau lien.",
    ),
});
export const changeEmailSchema = z.object({
  email,
  current_password: z
    .string()
    .min(1, "Saisissez votre mot de passe.")
    .max(128, "128 caractères maximum."),
});
export type PasswordFieldsInput = z.infer<typeof passwordFieldsSchema>;
export type ChangePasswordInput = z.infer<typeof changePasswordSchema>;
export type ChangeEmailInput = z.infer<typeof changeEmailSchema>;
export type ForgotPasswordInput = z.infer<typeof forgotPasswordSchema>;
export type ResetPasswordInput = z.infer<typeof resetPasswordSchema>;

export const confirmEmailSchema = z.object({
  token: z
    .string()
    .regex(
      /^[A-Za-z0-9_-]{43}$/,
      "Le lien de confirmation est invalide ou a expiré. Demandez un nouveau lien.",
    ),
});
