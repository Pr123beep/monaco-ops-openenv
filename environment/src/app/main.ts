import { applyAutocorrect, getAutocorrectHints } from "../shared/autocorrect.js";
import { DEFAULT_SETTINGS } from "../shared/contracts.js";

async function fetchJson<T>(url: string): Promise<T | null> {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

function renderShell() {
  const root = document.querySelector<HTMLDivElement>("#workspace-shell");
  if (!root) {
    return;
  }

  root.innerHTML = `
    <section class="panel">
      <h2>Starter status</h2>
      <p>This placeholder shell is here only to keep the project runnable before Monaco is integrated.</p>
      <div class="pill-row" role="tablist">
        ${getAutocorrectHints()
          .map((hint) => `<span class="pill">${hint}</span>`)
          .join("")}
      </div>
    </section>
    <section class="panel">
      <h2>Why this bundle exists</h2>
      <ul>
        <li>Multi-target TypeScript with an ESM package boundary.</li>
        <li>Browser shell and Node server compiled from separate tsconfig files.</li>
        <li>Shared deterministic helpers for settings and auto-correction.</li>
        <li>Seed workspace files that should become Monaco tabs.</li>
      </ul>
    </section>
    <section class="panel">
      <h2>Autocorrect preview</h2>
      <p><code>${applyAutocorrect("funtion demo() { retrun teh value; }")}</code></p>
      <p>Saved default theme: <strong>${DEFAULT_SETTINGS.theme}</strong></p>
    </section>
  `;
}

async function bootstrap() {
  renderShell();

  const health = await fetchJson<{ ok: boolean; message: string }>("/health");
  const status = document.querySelector<HTMLElement>("#health-status");
  if (status) {
    status.textContent = health?.ok ? "ready for implementation" : "server missing";
  }
}

void bootstrap();
