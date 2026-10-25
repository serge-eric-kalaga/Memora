/** Générer ou comparer le SDK sans modifier les fichiers versionnés en mode --check. */
import { createClient } from "@hey-api/openapi-ts";
import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";
import config from "../openapi-ts.config.mjs";

const check = process.argv.includes("--check");
const temporary = check ? await mkdtemp(join(tmpdir(), "template-api-")) : null;
const output = temporary || config.output.path;

async function files(directory) {
  const entries = await readdir(directory, { withFileTypes: true }).catch(
    (error) => {
      if (error.code === "ENOENT") return [];
      throw error;
    },
  );
  const paths = await Promise.all(
    entries.map((entry) => {
      const path = join(directory, entry.name);
      return entry.isDirectory() ? files(path) : [path];
    }),
  );
  return paths.flat().sort();
}

try {
  // Conserver les mêmes imports relatifs vers le runtime server-only dans le dossier temporaire.
  const plugins = config.plugins.map((plugin) =>
    typeof plugin === "object" && plugin.runtimeConfigPath
      ? {
          ...plugin,
          runtimeConfigPath: join(
            output,
            relative(config.output.path, resolve(plugin.runtimeConfigPath)),
          ),
        }
      : plugin,
  );
  await createClient({
    ...config,
    plugins,
    output: { ...config.output, path: output },
  });
  if (check) {
    const expected = await files(output);
    const committed = await files(config.output.path);
    const names = (paths, base) => paths.map((path) => relative(base, path));
    let current =
      JSON.stringify(names(expected, output)) ===
      JSON.stringify(names(committed, config.output.path));
    if (current) {
      const matches = await Promise.all(
        expected.map(async (path) => {
          const generated = await readFile(path);
          const existing = await readFile(
            join(config.output.path, relative(output, path)),
          );
          return generated.equals(existing);
        }),
      );
      current = matches.every(Boolean);
    }
    if (!current) {
      console.error(
        "Client API obsolète : exportez OpenAPI puis exécutez npm run api:generate.",
      );
      process.exitCode = 1;
    } else {
      console.log("Client API généré à jour.");
    }
  }
} finally {
  if (temporary) await rm(temporary, { recursive: true, force: true });
}
