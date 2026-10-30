import React, { useState } from 'react';
import { createDonation, DonationError, type DonationField, type DonationReceipt } from '../api';
import {
  DONATION_CURRENCY,
  DONATION_FUNDS,
  DONATION_PRESETS,
  type FundId,
} from '../config';
import { useI18n } from '../i18n';
import { describeApiError } from '../utils/errors';
import {
  currencySymbol,
  formatCardNumber,
  formatCvc,
  formatExpiry,
  formatMoney,
  parseAmount,
  validateAmount,
  validateCardNumber,
  validateCvc,
  validateExpiry,
} from '../utils/donation';

type FieldErrors = Partial<Record<DonationField, string>>;
type Status = 'idle' | 'loading' | 'success' | 'error';

interface DonationFormProps {
  /** Called after the backend accepted the payment, e.g. to refresh the statistics. */
  onDonated?: (receipt: DonationReceipt) => void;
}

export const DonationForm: React.FC<DonationFormProps> = ({ onDonated }) => {
  const { m } = useI18n();
  const t = m.donate;
  const [amount, setAmount] = useState('25');
  const [fund, setFund] = useState<FundId>(DONATION_FUNDS[0].id);
  const [cardNumber, setCardNumber] = useState('');
  const [expiry, setExpiry] = useState('');
  const [cvc, setCvc] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [status, setStatus] = useState<Status>('idle');
  const [serverError, setServerError] = useState('');
  const [receipt, setReceipt] = useState<DonationReceipt | null>(null);

  /** Wraps a field setter so that editing a field also clears that field's old error. */
  const edit = (field: DonationField, setter: (value: string) => void) => (value: string) => {
    setter(value);
    setErrors((prev) => (prev[field] ? { ...prev, [field]: undefined } : prev));
  };

  const parsedAmount = parseAmount(amount);
  const fundLabel = (id: string) => (t.funds as Record<string, string>)[id] ?? id;

  const validate = (): FieldErrors => {
    const found: FieldErrors = {};
    const checks: [DonationField, string | null][] = [
      ['amount', validateAmount(amount, t.validation, DONATION_CURRENCY)],
      ['card_number', validateCardNumber(cardNumber, t.validation)],
      ['card_expiry', validateExpiry(expiry, t.validation)],
      ['card_cvc', validateCvc(cvc, t.validation)],
    ];
    for (const [field, message] of checks) if (message) found[field] = message;
    return found;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (status === 'loading') return;
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0 || parsedAmount === null) return;

    setStatus('loading');
    setServerError('');
    try {
      const result = await createDonation({
        amount: parsedAmount,
        target_fund: fund,
        card_number: cardNumber,
        card_expiry: expiry,
        card_cvc: cvc,
      });
      // The card data is not needed any more: do not keep it in the component state.
      setCardNumber('');
      setExpiry('');
      setCvc('');
      setReceipt(result);
      setStatus('success');
      onDonated?.(result);
    } catch (err) {
      const failure = err as DonationError;
      setErrors(failure.fieldErrors ?? {});
      setServerError(
        failure.code === 'invalid_input'
          ? t.errors.rejected
          : failure.code === 'network'
            ? t.errors.network
            : describeApiError(failure, m)
      );
      setStatus('error');
    }
  };

  const reset = () => {
    setReceipt(null);
    setErrors({});
    setServerError('');
    setStatus('idle');
  };

  // TODO(Tamara): animation for the success state (e.g. a lit candle or a fade-in of the receipt).
  if (status === 'success' && receipt) {
    return (
      <div className="card donate-success" role="status">
        <span className="icon-circle" aria-hidden="true">✓</span>
        <h2>{t.success.title}</h2>
        <p className="muted">{t.success.text}</p>
        <dl className="receipt">
          <div><dt>{t.success.amount}</dt><dd>{formatMoney(receipt.amount, receipt.currency)}</dd></div>
          <div><dt>{t.success.fund}</dt><dd>{fundLabel(receipt.target_fund)}</dd></div>
          <div><dt>{t.success.card}</dt><dd>•••• {receipt.card_last4}</dd></div>
          <div><dt>{t.success.reference}</dt><dd>{receipt.transaction_reference}</dd></div>
          {receipt.minecraft_blocks_awarded > 0 && (
            <div><dt>{t.success.blocks}</dt><dd>{receipt.minecraft_blocks_awarded}</dd></div>
          )}
        </dl>
        <button className="btn btn-secondary" onClick={reset}>{t.success.another}</button>
      </div>
    );
  }

  return (
    <form className="card donate-form" onSubmit={handleSubmit} noValidate>
      <h2>{t.form.title}</h2>

      {/* TODO(Tamara): accessibility pass: aria-describedby for every error, focus the first invalid field, aria-live region for the status. */}
      <div className="field">
        <label htmlFor="donate-amount">{t.form.amount}, {currencySymbol(DONATION_CURRENCY)}</label>
        <input
          id="donate-amount"
          className="input"
          inputMode="decimal"
          autoComplete="off"
          value={amount}
          onChange={(e) => edit('amount', setAmount)(e.target.value)}
          aria-invalid={Boolean(errors.amount)}
        />
        <div className="chips">
          {DONATION_PRESETS.map((value) => (
            <button
              type="button"
              key={value}
              className={parsedAmount === value ? 'chip active' : 'chip'}
              onClick={() => edit('amount', setAmount)(String(value))}
            >
              {formatMoney(value, DONATION_CURRENCY)}
            </button>
          ))}
        </div>
        {errors.amount && <p className="field-error">{errors.amount}</p>}
      </div>

      <div className="field">
        <label htmlFor="donate-fund">{t.form.fund}</label>
        <select id="donate-fund" className="input" value={fund} onChange={(e) => setFund(e.target.value as FundId)}>
          {DONATION_FUNDS.map((f) => (
            <option key={f.id} value={f.id}>{fundLabel(f.id)}</option>
          ))}
        </select>
        {fund === 'minecraft_church' && <p className="muted small">{t.form.minecraftHint}</p>}
      </div>

      <div className="field">
        <label htmlFor="donate-card">{t.form.cardNumber}</label>
        <input
          id="donate-card"
          className="input"
          inputMode="numeric"
          autoComplete="off"
          placeholder="0000 0000 0000 0000"
          value={cardNumber}
          onChange={(e) => edit('card_number', setCardNumber)(formatCardNumber(e.target.value))}
          aria-invalid={Boolean(errors.card_number)}
        />
        {errors.card_number && <p className="field-error">{errors.card_number}</p>}
      </div>

      {/* TODO(Tamara): mobile layout of the card row (expiry and CVC) on narrow screens, bigger tap targets. */}
      <div className="field-row">
        <div className="field">
          <label htmlFor="donate-expiry">{t.form.expiry}</label>
          <input
            id="donate-expiry"
            className="input"
            inputMode="numeric"
            autoComplete="off"
            placeholder={t.form.expiryPlaceholder}
            value={expiry}
            onChange={(e) => edit('card_expiry', setExpiry)(formatExpiry(e.target.value, expiry))}
            aria-invalid={Boolean(errors.card_expiry)}
          />
          {errors.card_expiry && <p className="field-error">{errors.card_expiry}</p>}
        </div>
        <div className="field">
          <label htmlFor="donate-cvc">{t.form.cvc}</label>
          <input
            id="donate-cvc"
            className="input"
            inputMode="numeric"
            autoComplete="off"
            type="password"
            placeholder="•••"
            value={cvc}
            onChange={(e) => edit('card_cvc', setCvc)(formatCvc(e.target.value))}
            aria-invalid={Boolean(errors.card_cvc)}
          />
          {errors.card_cvc && <p className="field-error">{errors.card_cvc}</p>}
        </div>
      </div>

      {/* TODO(Tamara): show server errors as a toast instead of an inline note. */}
      {status === 'error' && serverError && <p className="form-error" role="alert">{serverError}</p>}

      <button className="btn btn-primary" type="submit" disabled={status === 'loading'}>
        {status === 'loading'
          ? t.form.processing
          : parsedAmount !== null
            ? `${t.form.submit} · ${formatMoney(parsedAmount, DONATION_CURRENCY)}`
            : t.form.submit}
      </button>
    </form>
  );
};
