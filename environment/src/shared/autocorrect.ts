const REPLACEMENTS: Array<[RegExp, string]> = [
  [/\bfuntion\b/g, "function"],
  [/\bretrun\b/g, "return"],
  [/\bteh\b/g, "the"],
  [/\bcosnt\b/g, "const"],
  [/\bpritn\b/g, "print"]
];

export function applyAutocorrect(input: string): string {
  return REPLACEMENTS.reduce((value, [pattern, replacement]) => {
    return value.replace(pattern, replacement);
  }, input);
}

export function getAutocorrectHints(): string[] {
  return [
    "funtion -> function",
    "retrun -> return",
    "teh -> the",
    "cosnt -> const",
    "pritn -> print"
  ];
}
