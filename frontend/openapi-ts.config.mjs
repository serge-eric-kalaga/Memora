import { fileURLToPath } from "node:url";

/** Génération locale et reproductible ; aucun serveur ni compte Hey API requis. */
const config = {
  input: fileURLToPath(new URL("../backend/openapi.json", import.meta.url)),
  output: {
    path: fileURLToPath(new URL("./src/lib/api/generated", import.meta.url)),
  },
  plugins: [
    "@hey-api/typescript",
    {
      name: "@hey-api/client-fetch",
      runtimeConfigPath: fileURLToPath(
        new URL("./src/lib/api/generated-runtime", import.meta.url),
      ),
    },
    "@hey-api/sdk",
  ],
};

export default config;
