# Plain language

A PR or issue is read by someone skimming in 30 seconds. These rules bind
whoever writes it, human or Claude.

They apply to every part of a pull request and every part of an issue, with one
exception: the "For Claude" fold-out at the bottom. That fold-out is where full
technical detail, exact values, and edge cases go, and it is exempt.

## What to write

- Give every sentence a job. A sentence earns its place when it changes what the
  reader does, watches for, or believes. Cut the rest.
- A PR or issue is a document, not a conversation. Open with what changed and
  end at the last fact. No background first, no recap, no handoff, no "next
  steps" that wait on a reply.
- A template wins on structure. Keep every line the template supplies and answer
  its prompts in place.
- Claim only what you earned. Say which parts you verified and which you infer,
  and keep the hedge where you genuinely do not know.

## How to write it

- One idea per sentence, 15 to 20 words on average.
- Use the most common word that is still exact: start, not commence; use, not
  utilize; about, not regarding. No idioms: name the literal action.
- Active voice, and name the actor: "the migration dropped `users.email`", not
  "the column was dropped".
- Never turn a verb into a noun: "validate the input", not "perform a validation
  of the input".
- Simple tenses: "I applied the migration", not "the migration has been
  applied".
- No clause hung off the end of a sentence with a comma and an "-ing" verb. That
  is where hedging collects.
- Keep the words that carry grammar. Keep every article, keep "that" after a
  verb, and spell out contractions: "does not", never "doesn't".
- Write numbers as digits: 3, not three.
- Expand an acronym on first use. Write "for example", not "e.g."
- Keep the exact technical term and define it once, in a short clause: "the
  write is idempotent, so running it twice changes nothing."
- Quote identifiers, paths, flags, and column names exactly, in backticks. Plain
  language governs the prose, never the literal text a reader has to match.
- One name per thing. If it is `users.email` in the summary, it is `users.email`
  in the checklist, not "the email column" and not "that field". Reuse the names
  the issue and the code already use. Do not coin new ones.
- Every line has to work read alone. No "see above", and no bare "this". Put a
  noun after it.
- More than 3 parallel items become a list, not a comma series. Steps and facts
  never share a list: facts go in the sentence above the steps.
- One line per paragraph. Do not hard-wrap. GitHub turns every newline in a PR
  or issue body into a line break, so wrapped prose renders as a ragged narrow
  column.
