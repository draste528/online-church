import React, { useState } from 'react';
import { createDonation, DonationError, type DonationField, type DonationReceipt } from '../api';
import {
  DONATION_CURRENCY,
  DONATION_FUNDS,
  DONATION_PRESETS,
  type FundId,
} from '../config';
import {
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
  const [amount, setAmount] = useState('500');
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
  const fundLabel = (id: string) => DONATION_FUNDS.find((f) => f.id === id)?.label ?? id;

  const validate = (): FieldErrors => {
    const found: FieldErrors = {};
    const checks: [DonationField, string | null][] = [
      ['amount', validateAmount(amount)],
      ['card_number', validateCardNumber(cardNumber)],
      ['card_expiry', validateExpiry(expiry)],
      ['card_cvc', validateCvc(cvc)],
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
      setServerError(failure.message);
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
        <h2>Благодарим за пожертвование!</h2>
        <p className="muted">Господь да благословит вас. Это демонстрационный платёж: деньги не списывались.</p>
        <dl className="receipt">
          <div><dt>Сумма</dt><dd>{formatMoney(receipt.amount, receipt.currency)}</dd></div>
          <div><dt>Фонд</dt><dd>{fundLabel(receipt.target_fund)}</dd></div>
          <div><dt>Карта</dt><dd>•••• {receipt.card_last4}</dd></div>
          <div><dt>Номер операции</dt><dd>{receipt.transaction_reference}</dd></div>
          {receipt.minecraft_blocks_awarded > 0 && (
            <div><dt>Блоков собора</dt><dd>{receipt.minecraft_blocks_awarded}</dd></div>
          )}
        </dl>
        <button className="btn btn-secondary" onClick={reset}>Сделать ещё одно пожертвование</button>
      </div>
    );
  }

  return (
    <form className="card donate-form" onSubmit={handleSubmit} noValidate>
      <h2>Данные платежа</h2>

      {/* TODO(Tamara): accessibility pass: aria-describedby for every error, focus the first invalid field, aria-live region for the status. */}
      <div className="field">
        <label htmlFor="donate-amount">Сумма, {DONATION_CURRENCY}</label>
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
        <label htmlFor="donate-fund">Куда направить</label>
        <select id="donate-fund" className="input" value={fund} onChange={(e) => setFund(e.target.value as FundId)}>
          {DONATION_FUNDS.map((f) => (
            <option key={f.id} value={f.id}>{f.label}</option>
          ))}
        </select>
      </div>

      <div className="field">
        <label htmlFor="donate-card">Номер карты</label>
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
          <label htmlFor="donate-expiry">Срок действия</label>
          <input
            id="donate-expiry"
            className="input"
            inputMode="numeric"
            autoComplete="off"
            placeholder="ММ/ГГ"
            value={expiry}
            onChange={(e) => edit('card_expiry', setExpiry)(formatExpiry(e.target.value, expiry))}
            aria-invalid={Boolean(errors.card_expiry)}
          />
          {errors.card_expiry && <p className="field-error">{errors.card_expiry}</p>}
        </div>
        <div className="field">
          <label htmlFor="donate-cvc">CVC</label>
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
          ? 'Обработка…'
          : parsedAmount !== null
            ? `Подтвердить оплату · ${formatMoney(parsedAmount, DONATION_CURRENCY)}`
            : 'Подтвердить оплату'}
      </button>
    </form>
  );
};
