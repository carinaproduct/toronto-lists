// Shared validation for event submissions.

export const TIME_ZONE = 'America/Toronto';

const LIMITS = {
  contact: 200,
  eventName: 200,
  registrationLink: 500,
  handles: 300,
  feedback: 2000,
};

// Today's date (YYYY-MM-DD) in Toronto, so "past event" checks match local time.
export function todayInToronto(now = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
}

export function isIsoDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const d = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === value;
}

function str(value) {
  return typeof value === 'string' ? value.trim() : '';
}

// Returns { ok: true, data } or { ok: false, errors: { field: message } }.
export function validateSubmission(body, now = new Date()) {
  const data = {
    contact: str(body?.contact),
    eventDate: str(body?.eventDate),
    eventName: str(body?.eventName),
    registrationLink: str(body?.registrationLink),
    handles: str(body?.handles),
    feedback: str(body?.feedback),
  };
  const errors = {};

  if (!data.contact) errors.contact = 'Please share an email or X handle.';
  if (!data.eventName) errors.eventName = 'Please add the event name.';
  if (!data.handles) errors.handles = 'Add the organizer handles, or "n/a".';

  if (!isIsoDate(data.eventDate)) {
    errors.eventDate = 'Please pick the event date.';
  } else if (data.eventDate < todayInToronto(now)) {
    errors.eventDate = 'This date has already passed.';
  }

  try {
    const url = new URL(data.registrationLink);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') throw new Error();
  } catch {
    errors.registrationLink = 'Please enter a full link, starting with https://';
  }

  for (const [field, max] of Object.entries(LIMITS)) {
    if (data[field].length > max && !errors[field]) {
      errors[field] = `Please keep this under ${max} characters.`;
    }
  }

  return Object.keys(errors).length ? { ok: false, errors } : { ok: true, data };
}
