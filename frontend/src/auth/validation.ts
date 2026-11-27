const PASSWORD_MAX_BYTES = 72;

export function usernameIssue(username: string): 'username_rule' | undefined {
  return /^[\p{L}\p{N}_.-]{3,50}$/u.test(username) ? undefined : 'username_rule';
}

export function passwordIssue(password: string, email = '', username = ''): 'password_rule' | 'identity_rule' | undefined {
  if (password.length < 10 || new TextEncoder().encode(password).length > PASSWORD_MAX_BYTES || !/\p{L}/u.test(password) || !/\d/u.test(password)) return 'password_rule';
  if ([email, username].filter(Boolean).some(value => value.toLowerCase() === password.toLowerCase())) return 'identity_rule';
  // The server's configurable common-password list remains authoritative.
}
export function passwordStrength(password: string): number {
  if (!password || passwordIssue(password)) return 0;
  return password.length >= 14 && /[^\p{L}\d]/u.test(password) ? 2 : 1;
}
