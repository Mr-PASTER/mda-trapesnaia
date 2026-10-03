import { execSync } from "node:child_process";
import { existsSync } from "node:fs";

const source = process.env.OPENAPI_URL ?? "http://localhost:8000/openapi.json";
execSync(`npx openapi-typescript ${source} -o src/api/schema.d.ts`, { stdio: "inherit" });
console.log("Generated src/api/schema.d.ts");
