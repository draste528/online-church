/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_ANALYTICS_URL?: string;
  readonly VITE_APPOINTMENTS_MOCK?: string;
  readonly VITE_AUTH_MOCK_ROLE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
