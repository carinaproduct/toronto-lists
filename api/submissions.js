import { timingSafeEqual } from 'node:crypto';
import { get, list } from '@vercel/blob';
import { isIsoDate } from '../lib/submission.js';

// GET /api/submissions?from=YYYY-MM-DD&to=YYYY-MM-DD
// Admin-only: requires `Authorization: Bearer <ADMIN_TOKEN>`.
// Returns the submissions whose event date falls in [from, to], sorted by date.
export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).json({ error: 'Method not allowed' });
  }
  res.setHeader('Cache-Control', 'no-store');

  if (!isAuthorized(req.headers.authorization)) {
    return res.status(401).json({ error: 'Wrong or missing admin token.' });
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

  return res.status(200).json({ submissions });
}

function isAuthorized(header) {
  const expected = process.env.ADMIN_TOKEN;
  if (!expected || !header?.startsWith('Bearer ')) return false;
  const given = Buffer.from(header.slice('Bearer '.length));
  const want = Buffer.from(expected);
  return given.length === want.length && timingSafeEqual(given, want);
}
