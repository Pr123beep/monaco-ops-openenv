export type ThemeName = "light" | "dark";

export interface AppSettings {
  theme: ThemeName;
  smoothTyping: boolean;
  autoCorrect: boolean;
  apiKey: string;
  apiBaseUrl: string;
}

export interface WorkspaceFileSummary {
  path: string;
  language: string;
  size: number;
}

export interface WorkspaceFileDocument extends WorkspaceFileSummary {
  content: string;
}

export interface AICompletionRequest {
  instruction: string;
  content: string;
  path: string;
}

export interface AICompletionResponse {
  completion: string;
}

export const DEFAULT_SETTINGS: AppSettings = {
  theme: "dark",
  smoothTyping: true,
  autoCorrect: true,
  apiKey: "",
  apiBaseUrl: "http://127.0.0.1:9800"
};
