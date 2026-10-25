import "server-only";
import type { CreateClientConfig } from "./generated/client.gen";

/** Barrière importée par le SDK généré : ses fonctions ne peuvent pas entrer dans un bundle navigateur. */
export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
});
