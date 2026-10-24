import { randomUUID } from 'node:crypto';
import { put } from '@vercel/blob';
import { validateSubmission } from '../lib/submission.js';

// POST /api/submit
// Accepts the form as urlencoded (no-JS fallback) or JSON. Each submission is
// stored as a private blob at submissions/<eventDate>/<timestamp>-<id>.json.
export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const wantsJson = (req.headers.accept || '').includes('application/json');
  const body = typeof req.body === 'object' && req.body !== null ? req.body : {};

  // Honeypot: real people never see this field, so a filled value is a bot.
  // Answer as if it worked so the bot moves on.
  if (body.website) return respondOk(res, wantsJson);

  const result = validateSubmission(body);
  if (!result.ok) {
    if (wantsJson) return res.status(400).json({ errors: result.errors });
    const lines = Object.values(result.errors).join('\n');
    return res.status(400).send(`Your submission needs a fix:\n\n${lines}\n\nGo back to correct it.`);
  }

  const submittedAt = new Date().toISOString();
  const id = randomUUID();
  const record = { id, submittedAt, ...result.data };

  try {
    await put(
      `submissions/${record.eventDate}/${submittedAt.replace(/[:.]/g, '-')}-${id}.json`,
      JSON.stringify(record, null, 2),
      { access: 'private', contentType: 'application/json', addRandomSuffix: false },
    );
  } catch (err) {
    console.error('Failed to store submission', err);
    const message = 'Something went wrong saving your event. Please try again in a minute.';
    return wantsJson ? res.status(500).json({ error: message }) : res.status(500).send(message);
  }

  return respondOk(res, wantsJson);
}

function respondOk(res, wantsJson) {
  if (wantsJson) return res.status(200).json({ ok: true });
  res.setHeader('Location', '/thanks');
  return res.status(303).end();
}
