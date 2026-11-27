import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import {
  closeSlot, getAppointments, getSlots, openSlot, updateAppointment,
  type Appointment, type AppointmentAction, type Slot,
} from '../appointments/api';
import { appointmentErrorKey, formatAppointmentDate, localDateInMoscow, moscowIso, personName, shiftDate, type AppointmentErrorKey } from '../appointments/presentation';
import { useI18n } from '../i18n';

export function CabinetAppointmentsPage() {
  const { user } = useAuth();
  const { m, locale } = useI18n();
  const a = m.appointments;
  const isPriest = user?.role === 'priest';
  const today = localDateInMoscow();
  const [date, setDate] = useState(today);
  const [time, setTime] = useState('10:00');
  const [items, setItems] = useState<Appointment[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<AppointmentErrorKey | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const actionLock = useRef(false);
  const generation = useRef(0);

  const load = useCallback(async (signal?: AbortSignal, preserveError = false) => {
    const id = ++generation.current;
    setLoading(true); if (!preserveError) setError(null);
    try {
      const [page, ownSlots] = await Promise.all([
        getAppointments(signal),
        isPriest && user?.user_id ? getSlots(user.user_id, date, signal) : Promise.resolve([] as Slot[]),
      ]);
      if (id === generation.current && !signal?.aborted) { setItems(page.items); setSlots(ownSlots); }
    } catch (reason) {
      if (id === generation.current && !signal?.aborted && !(reason instanceof Error && reason.name === 'AbortError')) setError(appointmentErrorKey(reason));
    } finally {
      if (id === generation.current && !signal?.aborted) setLoading(false);
    }
  }, [date, isPriest, user?.user_id]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => { controller.abort(); generation.current++; };
  }, [load]);

  async function mutate(action: () => Promise<unknown>, success: string) {
    if (actionLock.current) return;
    actionLock.current = true; setBusy(true); setError(null); setNotice(null);
    try { await action(); setNotice(success); await load(); }
    catch (reason) {
      const key = appointmentErrorKey(reason);
      setError(key);
      if (key === 'conflict' || key === 'slotTaken' || key === 'slotExists' || key === 'slotNotClosable' || key === 'invalidTransition') await load(undefined, true);
    } finally { actionLock.current = false; setBusy(false); }
  }

  async function addSlot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user?.user_id) return;
    await mutate(() => openSlot(moscowIso(date, time)), a.slotOpened);
  }

  function allowedActions(item: Appointment): AppointmentAction[] {
    const start = new Date(item.scheduled_at).getTime();
    const now = Date.now();
    if (item.status === 'requested' && now < start) return ['approved', 'rejected'];
    if (item.status === 'approved' && now >= start + 30 * 60 * 1000) return ['completed'];
    return [];
  }

  return <section className="appointments-page">
    <header className="appointments-heading"><div><h1>{isPriest ? a.priestCabinetTitle : a.myAppointments}</h1>
      <p>{isPriest ? a.priestCabinetIntro : a.parishionerCabinetIntro}</p></div>
      {!isPriest && <Link className="btn" to="/appointments">{a.newAppointment}</Link>}
    </header>

    {isPriest && <section className="card appointment-slot-management">
      <h2>{a.manageSlots}</h2><p className="appointment-timezone">{a.timezone}</p>
      <form className="appointment-slot-create" onSubmit={addSlot} aria-busy={busy}>
        <label className="appointment-field"><span>{a.date}</span><input type="date" value={date} min={today} max={shiftDate(today, 60)} onChange={event => setDate(event.target.value)} disabled={busy} required /></label>
        <label className="appointment-field"><span>{a.time}</span><input type="time" step="1800" value={time} onChange={event => setTime(event.target.value)} disabled={busy} required /></label>
        <button className="btn" disabled={busy}>{a.openSlot}</button>
      </form>
      <h3>{a.slotsForDate}</h3>
      {loading ? <p role="status">{a.loading}</p> : slots.length === 0 ? <p>{a.noManagedSlots}</p> : <ul className="appointment-slot-list">
        {slots.map(slot => <li key={slot.slot_id}>
          <span>{formatAppointmentDate(slot.scheduled_at, locale)}</span>
          <span className={`appointment-slot-state ${slot.is_free ? 'free' : 'busy'}`}>{slot.is_free ? a.free : a.occupied}</span>
          {slot.is_free && <button className="btn btn-secondary" disabled={busy} onClick={() => void mutate(() => closeSlot(slot.slot_id), a.slotClosed)}>{a.closeSlot}</button>}
        </li>)}
      </ul>}
    </section>}

    <section className="appointment-list-section"><h2>{isPriest ? a.assignedRequests : a.myAppointments}</h2>
      {loading ? <p role="status">{a.loading}</p> : items.length === 0 ? <p className="card appointment-empty">{a.noAppointments}</p> : <div className="appointment-list">
        {items.map(item => <article className="card appointment-card" key={item.appointment_id}>
          <div className="appointment-card-heading"><strong>{formatAppointmentDate(item.scheduled_at, locale)} <span className="appointment-timezone">{a.moscowTime}</span></strong>
            <span className={`appointment-status status-${item.status}`}>{a.statuses[item.status]}</span></div>
          <dl className="appointment-details">
            <div><dt>{isPriest ? a.parishioner : a.priest}</dt><dd>{personName(isPriest ? item.parishioner : item.priest)}</dd></div>
            <div><dt>{a.type}</dt><dd>{a.types[item.appointment_type]}</dd></div>
          </dl>
          {isPriest && allowedActions(item).length > 0 && <div className="appointment-actions">
            {allowedActions(item).map(action => <button className="btn btn-secondary" key={action} disabled={busy} onClick={() => void mutate(() => updateAppointment(item.appointment_id, action), a.actionDone)}>{a.actions[action]}</button>)}
          </div>}
        </article>)}
      </div>}
    </section>
    {error && <div className="appointment-page-error" role="alert"><span>{a.errors[error]}</span>
      <button type="button" className="btn btn-secondary" disabled={loading} onClick={() => void load()}>{a.retry}</button></div>}
    {notice && <p role="status" className="appointment-confirmation">{notice}</p>}
  </section>;
}
