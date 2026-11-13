export interface User {
  user_id: string;
  username: string;
  email: string;
  role: string;
  first_name?: string;
  last_name?: string;
  birth_year?: number | null;
  city?: string | null;
  acquisition_source?: string | null;
  preferred_language?: string;
  analytics_consent?: boolean;
}
export interface Credentials { email: string; password: string }
export interface Registration extends Credentials {
  username: string;
  first_name?: string;
  last_name?: string;
  analytics_consent: boolean;
  birth_year?: number;
  city?: string;
  acquisition_source?: string;
  preferred_language?: string;
}
export type ProfileUpdate = Pick<User, 'first_name' | 'last_name' | 'birth_year' | 'city' | 'preferred_language' | 'analytics_consent'>;
export interface TokenReply { access_token: string; token_type: string; expires_in: number; role: string }
