import type { NextConfig } from "next";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

// Configuration locale centralisée à la racine ; Compose injecte déjà ces variables.
const envFile = resolve(process.cwd(), "../.env.dev");
if (process.env.MEMORA_LOCAL !== "1" && process.env.NODE_ENV !== "production" && existsSync(envFile)) {
  process.loadEnvFile(envFile);
}

const nextConfig: NextConfig = {
  output: "standalone",
  async headers() {
    return [
      {
        source: "/confirmer-email",
        headers: [{ key: "Referrer-Policy", value: "no-referrer" }],
      },
      {
        source: "/reinitialiser-mot-de-passe",
        headers: [{ key: "Referrer-Policy", value: "no-referrer" }],
      },
    ];
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      // Tailwind ne transforme que son point d’entrée ; préserver les CSS Modules natifs.
      "globals.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
