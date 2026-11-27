import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { createAppointment, getAppointments, getPriests, getSlots, type AppointmentType, type Priest, type Slot } from '../appointments/api';
import { appointmentErrorKey, formatAppointmentDate, localDateInMoscow, personName, shiftDate, type AppointmentErrorKey } from '../appointments/presentation';
import { useI18n } from '../i18n';

export function AppointmentsPage() {
  const { m, locale } = useI18n();
  const a = m.appointments;
  const today = localDateInMoscow();
  const [date, setDate] = useState(today);
  const [priests, setPriests] = useState<Priest[]>([]);
  const [priestId, setPriestId] = useState('');
  const [slots, setSlots] = useState<Slot[]>([]);
  const [slotId, setSlotId] = useState('');
  const [type, setType] = useState<AppointmentType>('pastoral_talk');
  const [loadingPriests, setLoadingPriests] = useState(true);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<AppointmentErrorKey | null>(null);
  const [fieldError, setFieldError] = useState(false);
  const [confirmation, setConfirmation] = useState(false);
  const [pendingRetry, setPendingRetry] = useState(false);
  const lock = useRef(false);
  const attempt = useRef<{ fingerprint: string; key: string; value: { priest_id: string; scheduled_at: string; appointment_type: AppointmentType } } | null>(null);
  const selection = useRef({ priestId, date });
  selection.current = { priestId, date };
  const generation = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoadingPriests(true);
    getPriests(controller.signal).then(items => {
      if (controller.signal.aborted) return;
      setPriests(items);
      setPriestId(current => current && items.some(item => item.user_id === current) ? current : items[0]?.user_id ?? '');
      setError(null);
    }).catch(reason => {
      if (reason?.name !== 'AbortError') setError(appointmentErrorKey(reason));
    }).finally(() => { if (!controller.signal.aborted) setLoadingPriests(false); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    setSlotId('');
    setConfirmation(false);
    if (!priestId || !date) { setSlots([]); setLoadingSlots(false); return; }
    const controller = new AbortController();
    const currentGeneration = ++generation.current;
    setLoadingSlots(true);
    setError(null);
    getSlots(priestId, date, controller.signal).then(items => {
      if (!controller.signal.aborted && currentGeneration === generation.current) setSlots(items.filter(item => item.is_free));
    }).catch(reason => {
      if (!controller.signal.aborted && reason?.name !== 'AbortError' && currentGeneration === generation.current) {
        setSlots([]);
        setError(appointmentErrorKey(reason));
      }
    }).finally(() => {
      if (!controller.signal.aborted && currentGeneration === generation.current) setLoadingSlots(false);
    });
    return () => controller.abort();
  }, [priestId, date]);

  async function refreshSlots(priest: string, day: string) {
    try {
      const result = await getSlots(priest, day);
      if (selection.current.priestId === priest && selection.current.date === day) setSlots(result.filter(item => item.is_free));
    } catch { /* The original conflict remains visible; the next explicit retry can reload. */ }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current) return;
    const selected = slots.find(item => item.slot_id === slotId);
    if (!pendingRetry && (!priestId || !date || !selected)) { setFieldError(true); return; }
    const value = pendingRetry && attempt.current
      ? attempt.current.value
      : { priest_id: priestId, scheduled_at: selected!.scheduled_at, appointment_type: type };
    const fingerprint = JSON.stringify(value);
    if (attempt.current?.fingerprint !== fingerprint) attempt.current = { fingerprint, key: crypto.randomUUID(), value };
    lock.current = true; setBusy(true); setError(null); setFieldError(false); setConfirmation(false);
    try {
      await createAppointment(value, attempt.current.key);
      attempt.current = null;
      setPendingRetry(false);
      setConfirmation(true);
      setSlotId('');
      await Promise.all([refreshSlots(priestId, date)]);
    } catch (reason) {
      const key = appointmentErrorKey(reason);
      setError(key);
      if (key === 'network' || key === 'unavailable') setPendingRetry(true);
      if (key === 'slotTaken' || key === 'conflict') {
        attempt.current = null;
        setPendingRetry(false);
        await Promise.all([refreshSlots(priestId, date), getAppointments().catch(() => undefined)]);
        setSlotId('');
      }
      // A network error or 503 retains the exact key and body for a safe retry.
    } finally { lock.current = false; setBusy(false); }
  }

  const availableTypes: AppointmentType[] = ['confession', 'pastoral_talk', 'baptism_counseling'];
  return <section className="appointments-page">
    <header className="appointments-heading"><div><h1>{a.bookingTitle}</h1><p>{a.bookingIntro}</p></div><Link className="btn btn-secondary" to="/cabinet/appointments">{a.myAppointments}</Link></header>
    <form className="card appointment-form" onSubmit={submit} aria-busy={busy}>
      <label className="appointment-field"><span>{a.priest}</span>
        <select value={priestId} onChange={event => setPriestId(event.target.value)} disabled={loadingPriests || busy || pendingRetry} required>
          <option value="">{loadingPriests ? a.loading : a.choosePriest}</option>
          {priests.map(priest => <option key={priest.user_id} value={priest.user_id}>{personName(priest)}</option>)}
        </select>
      </label>
      {!loadingPriests && priests.length === 0 && <p role="status" className="appointment-empty">{a.noPriests}</p>}
      <label className="appointment-field"><span>{a.date}</span>
        <input type="date" value={date} min={today} max={shiftDate(today, 60)} onChange={event => setDate(event.target.value)} disabled={busy || pendingRetry} required />
      </label>
      <p className="appointment-timezone">{a.timezone}</p>
      <fieldset className="appointment-slot-picker" disabled={loadingSlots || busy || pendingRetry || !priestId}>
        <legend>{a.time}</legend>
        {loadingSlots ? <p role="status">{a.loadingSlots}</p> : slots.length === 0 ? <p>{a.noSlots}</p> : <div className="appointment-slot-grid">
          {slots.map(slot => <label className={`appointment-slot${slotId === slot.slot_id ? ' selected' : ''}`} key={slot.slot_id}>
            <input type="radio" name="appointment-slot" value={slot.slot_id} checked={slotId === slot.slot_id} onChange={() => { setSlotId(slot.slot_id); setConfirmation(false); }} />
            <span>{formatAppointmentDate(slot.scheduled_at, locale)}</span>
          </label>)}
        </div>}
      </fieldset>
      <label className="appointment-field"><span>{a.type}</span>
        <select value={type} onChange={event => { setType(event.target.value as AppointmentType); setConfirmation(false); }} disabled={busy || pendingRetry}>
          {availableTypes.map(option => <option value={option} key={option}>{a.types[option]}</option>)}
        </select>
      </label>
      {fieldError && <p role="alert" className="field-error">{a.selectSlot}</p>}
      {error && <p role="alert" className="field-error">{a.errors[error]}</p>}
      {confirmation && <p role="status" className="appointment-confirmation">{a.sent} <Link to="/cabinet/appointments">{a.viewAppointments}</Link></p>}
      <button className="btn" type="submit" disabled={busy || loadingPriests || (!pendingRetry && (loadingSlots || !priests.length || !slots.length))}>{busy ? a.sending : pendingRetry ? a.retry : a.send}</button>
    </form>
  </section>;
}
