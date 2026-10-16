import type { ApiError } from '../api';
import type { Messages } from '../i18n/ru';

/** Text for a failed request in the current language; a message written by the backend is shown as it is. */
export function describeApiError(err: ApiError, m: Messages): string {
  if (err.detail) return err.detail;
  switch (err.code) {
    case 'network':
      return m.errors.network;
    case 'empty_reply':
      return m.errors.emptyReply;
    case 'invalid_input':
      return m.errors.invalidMessage;
    default:
      return m.errors.http(err.status ?? 0);
  }
}
