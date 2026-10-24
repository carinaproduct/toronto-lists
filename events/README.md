# Toronto Tech Events

The list behind the [Toronto Tech Events page](https://claude.ai/artifact/NT9MzP2UpMuBosMkeSwMwF): in-person GTA tech events for the next six weeks, with picks for an AI product and marketing lead. A scheduled Claude session refreshes it every Monday morning.

## Files

- `collect.py`: pulls raw candidates from the Luma location feed and the Luma calendars in `luma_calendars.txt`, Eventbrite's Toronto keyword pages, Meetup search and the groups in `meetup_groups.txt`, and buildersundays.ca. Writes `candidates.json` (not committed).
- `events.json`: the curated list. Each event has a category, a `pick` flag and a one-line `why`.
- `reviewed.json`: candidate keys already reviewed and left out, so they aren't shown again.
- `submitted.json`: Builder Sundays dates already sent to the submission form.
- `review.py`: lists new candidates, then applies the decisions about them.
- `build_page.py` + `page_template.html`: build the page from `events.json`, dropping past events.

## Weekly refresh

1. `python3 -I events/collect.py --days 42 --out events/candidates.json` (about 6 minutes).
2. `python3 -I events/review.py`. Read every likely-tech candidate and skim the other titles.
3. Keep events that are in person, in the GTA, tech-relevant and open to the public. Drop pure socials and fitness, student-only or recruiting-only events, generic paid "networking" series (Startup Valley, Nomad Global Hub and similar), courses and webinars, and repeats of events already on the list. Mark `pick: true` for substantive talks, strong hosts, or good founder, VC or AI networking. Mark generic mixers `false`.
4. Write the kept events to a decisions file and run `python3 -I events/review.py --apply <file>`.
5. Check the sources the collector can't reach and add any new tech events to `events.json` by hand: brainstation.io/events (Toronto), eventstoronto.ca, MaRS (marsdd.com/events), cohere.com/events, and a web search for big Toronto tech events in the next six weeks.
6. Send any Builder Sundays date in `events.json` that isn't in `submitted.json` to the submission form, then record it in `submitted.json`:
   `curl -X POST https://toronto-lists-dun.vercel.app/api/submit -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"contact":"seeded by Carina from buildersundays.ca","eventDate":"YYYY-MM-DD","eventName":"Builder Sundays at Shopify (12-5 PM, 620 King St W)","registrationLink":"https://buildersundays.ca/products/toronto","handles":"Shopify"}'`
7. `python3 -I events/build_page.py`, then republish `events/toronto-tech-events.html` to the page's URL above.
8. Commit `events/` and push to `main`.

To watch a new community, add its Luma calendar id to `luma_calendars.txt` or its Meetup urlname to `meetup_groups.txt`.
