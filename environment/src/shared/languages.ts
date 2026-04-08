const EXTENSION_MAP = new Map<string, string>([
  [".ts", "typescript"],
  [".tsx", "typescript"],
  [".js", "javascript"],
  [".jsx", "javascript"],
  [".json", "json"],
  [".css", "css"],
  [".html", "html"],
  [".md", "markdown"],
  [".py", "python"]
]);

export function detectLanguage(path: string): string {
  const lower = path.toLowerCase();
  for (const [extension, language] of EXTENSION_MAP.entries()) {
    if (lower.endsWith(extension)) {
      return language;
    }
  }
  return "plaintext";
}
