# toronto-lists

Submission form for a weekly list of in-person Toronto tech events posted on X
([@carinaproduct](https://x.com/carinaproduct)). Modelled on Michelle Fang's SF
events form.

## Pages

- `/` — the public submission form (link this from X)
- `/thanks` — confirmation page
- `/admin` — private list builder: enter the admin token, pick a week, untick
  anything you don't want, and copy the generated thread draft

## How it works

Static pages in `public/`, two Vercel functions in `api/`:

- `POST /api/submit` validates a submission (`lib/submission.js`) and saves it
  as a **private** Vercel Blob at `submissions/<eventDate>/<timestamp>-<id>.json`.
  A hidden honeypot field drops bot submissions.
- `GET /api/submissions?from=YYYY-MM-DD&to=YYYY-MM-DD` returns submissions for
  that date range. Requires `Authorization: Bearer <ADMIN_TOKEN>`.

## Deploy (Vercel)

1. Import this repo as a Vercel project (no framework, no build command).
2. In the project, go to **Storage → Create → Blob**, choose **private** access,
   and connect it. This sets `BLOB_STORE_ID`, and the functions authenticate
   with the project's Vercel OIDC token (no read-write token needed).
3. Add an `ADMIN_TOKEN` environment variable set to a long random string
   (for example the output of `openssl rand -hex 24`).
4. Redeploy, then put the site URL in your X bio or pinned post.

## Editing the copy

All wording (rules, posting time, X handle) lives directly in
`public/index.html` and `public/thanks.html`.
