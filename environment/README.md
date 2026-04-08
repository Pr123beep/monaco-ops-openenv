# Monaco Ops Starter

This starter intentionally stops at the project scaffold. The workspace already has:

- an ESM `package.json`
- split TypeScript configs for browser and Node targets
- a tiny Node HTTP server in `src/node/server.ts`
- shared contracts and deterministic auto-correction helpers in `src/shared/`
- seeded settings and workspace files under `data/`

The missing work is the actual Monaco-powered editor application:

- integrate Monaco with a production build that still works in ESM mode
- finish the JSON APIs for settings, files, and AI completion
- wire the browser shell into those APIs with a real multi-file tabbed editor
- persist settings and file changes under `data/`

Keep the project in TypeScript + Node.js and keep `package.json` set to `"type": "module"`.
