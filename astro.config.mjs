import { defineConfig } from "astro/config";

const repositoryName = process.env.GITHUB_REPOSITORY?.split("/")[1];
const base = process.env.BASE_PATH || (repositoryName ? `/${repositoryName}` : "/");

export default defineConfig({
  output: "static",
  site: process.env.SITE_URL || "http://localhost:4321",
  base,
});

