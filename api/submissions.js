import { timingSafeEqual } from 'node:crypto';
import { get, list } from '@vercel/blob';
import { isIsoDate } from '../lib/submission.js';

// GET /api/submissions?from=YYYY-MM-DD&to=YYYY-MM-DD
// Requires `Authorization: Bearer <token>`:
//   ADMIN_TOKEN returns full submissions, including the submitter's contact and feedback.
//   BOT_TOKEN returns only the public event fields, for a bot drafting the weekly thread.
// Returns the submissions whose event date falls in [from, to], sorted by date.
export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).json({ error: 'Method not allowed' });
  }
  res.setHeader('Cache-Control', 'no-store');

  const role = roleFor(req.headers.authorization);
  if (!role) {
    return res.status(401).json({ error: 'Wrong or missing token.' });
  }

  const { from, to } = req.query;
  if (!isIsoDate(from) || !isIsoDate(to) || from > to) {
    return res.status(400).json({ error: 'Pass from and to as YYYY-MM-DD.' });
  }

  // Pathnames start with submissions/<eventDate>/, so filter before downloading.
  const pathnames = [];
  let cursor;
  do {
    const page = await list({ prefix: 'submissions/', cursor, limit: 1000 });
    for (const blob of page.blobs) {
      const eventDate = blob.pathname.split('/')[1];
      if (eventDate >= from && eventDate <= to) pathnames.push(blob.pathname);
    }
    cursor = page.hasMore ? page.cursor : undefined;
  } while (cursor);

  const submissions = (
    await Promise.all(
      pathnames.map(async (pathname) => {
        const blob = await get(pathname, { access: 'private' });
        if (!blob || blob.statusCode !== 200) return null;
        return JSON.parse(await new Response(blob.stream).text());
      }),
    )
  )
    .filter(Boolean)
    .sort((a, b) => a.eventDate.localeCompare(b.eventDate) || a.submittedAt.localeCompare(b.submittedAt));

  if (role === 'bot') {
    return res.status(200).json({ submissions: submissions.map(toPublic) });
  }
  return res.status(200).json({ submissions });
}

// Only what goes into a public post: never the submitter's contact or feedback.
function toPublic({ id, eventDate, eventName, registrationLink, handles }) {
  return { id, eventDate, eventName, registrationLink, handles };
}

function roleFor(header) {
  if (!header?.startsWith('Bearer ')) return null;
  const given = header.slice('Bearer '.length);
  if (matches(given, process.env.ADMIN_TOKEN)) return 'admin';
  if (matches(given, process.env.BOT_TOKEN)) return 'bot';
  return null;
}

function matches(given, expected) {
  if (!expected) return false;
  const a = Buffer.from(given);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}
