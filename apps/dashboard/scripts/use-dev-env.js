const fs = require("node:fs");
const path = require("node:path");

const projectRoot = path.resolve(__dirname, "..");
const devEnvPath = path.join(projectRoot, ".env.development");
const prodLocalPath = path.join(projectRoot, ".env.production.local");

function main() {
  if (!fs.existsSync(devEnvPath)) {
    console.warn(
      "[use-dev-env] Skipping: .env.development not found in apps/dashboard",
    );
    return;
  }

  // Do not overwrite an existing production-local file.
  if (fs.existsSync(prodLocalPath)) {
    console.log(
      "[use-dev-env] .env.production.local already exists; leaving it untouched.",
    );
    return;
  }

  fs.copyFileSync(devEnvPath, prodLocalPath);
  console.log(
    "[use-dev-env] Copied .env.development to .env.production.local for this run.",
  );
}

main();
