/** Vérifications à la compilation : un SDK devenu permissif fait échouer les @ts-expect-error. */
import type { Client } from "../src/lib/api/generated/client";
import {
  authLogin,
  changeEmail,
  changePassword,
  getProfilePhoto,
  uploadProfilePhoto,
} from "../src/lib/api/generated/sdk.gen";

// Cette fonction n’est jamais exécutée ; npm run typecheck vérifie uniquement ses contrats.
export function verifyGeneratedContracts(client: Client) {
  void authLogin({
    client,
    body: { username: "example", password: "example" },
  });
  // @ts-expect-error Le mot de passe de connexion est obligatoire.
  void authLogin({ client, body: { username: "example" } });
  void changePassword({
    client,
    body: {
      current_password: "example",
      new_password: "example",
      // @ts-expect-error Un champ inconnu doit être refusé à la compilation.
      unexpected: true,
    },
  });
  // Les champs writeOnly restent requis dans les types d’entrée générés.
  void changeEmail({
    client,
    body: { email: "example@example.com", current_password: "example" },
  });
  // @ts-expect-error Le mot de passe actuel ne doit pas disparaître du contrat d’entrée.
  void changeEmail({ client, body: { email: "example@example.com" } });
  // @ts-expect-error Une photo doit être un Blob/File, pas une chaîne.
  void uploadProfilePhoto({ client, body: { photo: "example.png" } });
  // @ts-expect-error Le paramètre du chemin doit être fourni.
  void getProfilePhoto({ client });
}
