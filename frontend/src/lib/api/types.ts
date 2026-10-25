/** Contrat du compte courant. Les dates du backend sont exprimées en UTC. */
import type { CurrentUserModel } from "./generated/types.gen";

// Projection explicite : les futurs champs privés du backend ne passent pas automatiquement au navigateur.
export type CurrentUser = Required<
  Pick<
    CurrentUserModel,
    | "username"
    | "email"
    | "email_verified_at"
    | "telephone"
    | "profile_photo_url"
    | "last_login_at"
  >
>;
export interface ApiEnvelope<T> {
  data: T;
  message?: string;
}
