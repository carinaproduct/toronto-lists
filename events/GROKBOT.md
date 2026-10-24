# Grok bot: weekly thread drafting

The Claude scheduled task finds and curates events every Monday morning (see `README.md`). The Grok bot does the posting half: it reads that list plus form submissions and drafts the thread on X.

## What the bot reads

1. **Curated events** (public, no login):
   `https://raw.githubusercontent.com/carinaproduct/toronto-lists/main/events/events.json`
   This updates when the Monday refresh branch is merged into `main`, so merge it before the bot runs.
2. **Form submissions**:
   `GET https://toronto-lists-dun.vercel.app/api/submissions?from=YYYY-MM-DD&to=YYYY-MM-DD`
   with the header `Authorization: Bearer <ADMIN_TOKEN>`. Only give the bot the token if it stores secrets privately.

## Instructions to paste into the bot

```
Every Monday at 11 AM ET, draft my weekly Toronto tech events thread for X and send it to me for approval. Do not post without my OK.

Data:
1. Curated events: GET https://raw.githubusercontent.com/carinaproduct/toronto-lists/main/events/events.json
   Fields: date (YYYY-MM-DD), time, name, venue, url, x_handles (list, no @), category, pick (true/false), why, price.
2. Submissions: GET https://toronto-lists-dun.vercel.app/api/submissions?from=<Monday>&to=<Sunday>
   Header: Authorization: Bearer <ADMIN_TOKEN>
   Fields: eventDate, eventName, registrationLink, handles. Never post the contact or feedback fields; they are private.

Pick the events:
- This week only, Monday to Sunday, Toronto time.
- Include every submission that is in person and tech-related.
- From the curated list, include events with pick = true. Lead with events hosted by known tech companies.
- Skip anything whose "why" says sold out, unless I ask for it. If "why" says approval, invite or waitlist, add "(request to join)" or "(waitlist)".
- Builder Sundays at Shopify is always in.
- Aim for 10 to 15 events. Merge duplicates (same event, same date).

Format (a thread, every post under 280 characters):
Post 1:
toronto tech events this week 🍁🧵

<2-3 standout events by name, lowercase, comma-separated> + <N> more

hosting something next week? submit it: toronto-lists-dun.vercel.app

Then one post per event, in date order:
Mon Oct 26, 5:30 PM
<event name>
<venue, if public>
by @handle @handle   (only handles you were given; never guess one)
<link without https://>

Style: lowercase in the first post is fine, plain hyphens, no em-dashes, no hashtags, no closing post.
```
