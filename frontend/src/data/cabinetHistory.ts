/** Sample activity shown until the account history endpoints are available. */
export type PrayerRequestType = 'health' | 'repose' | 'sorokoust' | 'moleben' | 'blessing';
export type PrayerRequestStatus = 'submitted' | 'accepted' | 'completed' | 'cancelled';

export interface PrayerRequestHistoryItem {
  id: string;
  type: PrayerRequestType;
  names: string[];
  status: PrayerRequestStatus;
  createdAt: string;
  donationAmount: number;
}

const MOCK_PRAYER_REQUESTS: PrayerRequestHistoryItem[] = [
  { id: 'demo-prayer-1', type: 'health', names: ['Анна', 'Михаил'], status: 'accepted', createdAt: '2026-09-30T09:15:00Z', donationAmount: 5 },
  { id: 'demo-prayer-2', type: 'repose', names: ['Мария'], status: 'completed', createdAt: '2026-09-28T14:40:00Z', donationAmount: 0 },
];

export async function loadPrayerRequestHistory(signal: AbortSignal): Promise<PrayerRequestHistoryItem[]> {
  if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
  return structuredClone(MOCK_PRAYER_REQUESTS);
}

export type DonationHistoryStatus = 'completed' | 'pending' | 'failed';
export type DonationFund = 'general' | 'temple_restoration' | 'choir' | 'charity' | 'minecraft_church';

export interface DonationHistoryItem {
  id: string;
  amount: number;
  currency: string;
  fund: DonationFund;
  status: DonationHistoryStatus;
  createdAt: string;
}

const MOCK_DONATIONS: DonationHistoryItem[] = [
  { id: 'demo-donation-1', amount: 25, currency: 'USD', fund: 'general', status: 'completed', createdAt: '2026-09-29T12:10:00Z' },
  { id: 'demo-donation-2', amount: 10, currency: 'USD', fund: 'charity', status: 'completed', createdAt: '2026-09-20T08:25:00Z' },
];

export async function loadDonationHistory(signal: AbortSignal): Promise<DonationHistoryItem[]> {
  if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
  return structuredClone(MOCK_DONATIONS);
}
