import { cp, mkdir } from "node:fs/promises";

const publicDir = new URL("../public", import.meta.url);
const distDir = new URL("../dist", import.meta.url);

await mkdir(distDir, { recursive: true });
await cp(publicDir, distDir, { force: true, recursive: true });
