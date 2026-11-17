# Changes to the "Dairy news and signal" scheduled task

Replace the matching parts of the v2 prompt with the text below. The task must run
against the `herdsignal` repo instead of the old profile repo.

## Phase 1, ledger (replace steps 1 and 3)

1. Read `ledger.json` from the repo as checked out. It is current: the repo copies each
   run's ledger back to `main` automatically.
3. At the end of the run, append today's items to `ledger.json` and commit it on your
   working branch along with the issue file.

## Phase 2 (edits)

- Split the consequence out of `body` into its own field, `why`. `body` says what happened.
  `why` says why it matters, without the words "Why it matters".
- Add `source_name` as it should read after "Read the source at", for example "USDA" or
  "the Federal Register".
- Style: no em dashes anywhere. Use commas, colons, parentheses or a new sentence.

## Phase 3, render (replace the whole phase)

Do not write HTML. Write one file, `issues/YYYY-MM-DD.json`, in the format shown in
`README.md`: the date, a two-sentence intro, and the kept items in priority order.
Then run `python3 build.py` to check it. If the build stops, fix the issue file it names
and run it again. Never edit `build.py`, the workflows, or `config.json`.

Operator QA never goes in the repo. Keep it for the Gmail draft in Phase 4.

## Phase 4, deliver (replace the whole phase)

1. Commit `issues/YYYY-MM-DD.json` and `ledger.json` and push your working branch.
   The repo publishes from there. Do not open a pull request.
2. Create a Gmail draft, not sent, containing the operator QA: items considered and kept,
   every drop with its reason, ledger collisions, any partly confirmed figure, and whether
   the push succeeded.
3. Do not email the brief to anyone.

## Hard constraints (replace the first and fifth lines)

- Publish by pushing the issue file. Never send email.
- No hand-written HTML. `build.py` owns the look.
