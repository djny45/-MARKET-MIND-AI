import { defineConfig } from "drizzle-kit";
import { config as loadEnv } from "dotenv";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

// Load .env.local / .env when present so local migration commands work, but
// always prefer a real environment variable (Vercel, CI, CI secrets).
for (const file of [".env.local", ".env"]) {
  const path = resolve(process.cwd(), file);
  if (existsSync(path)) loadEnv({ path, override: false });
}

const url = process.env.DATABASE_URL?.trim();

// Migration-history operations such as "drizzle-kit up" and "check" are local
// file operations and must work without a database. Database-writing commands
// still require a real DATABASE_URL and will fail closed when it is absent.
export default defineConfig({
  dialect: "postgresql",
  schema: "./src/db/schema.ts",
  ...(url ? { dbCredentials: { url } } : {}),
});
