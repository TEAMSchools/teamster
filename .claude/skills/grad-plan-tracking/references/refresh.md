# Running the grad plan refresh

The full "before you use it" procedure, for a master-scheduling push or any time
Teaching and Learning needs current numbers. Newark and Camden only — Paterson
and Miami have no PowerSchool grad plan data (see the doc's "Decisions").

## Run PowerSchool's Data Capture, then refresh the sheet

Follow the doc's
[What triggers it](../../../docs/models/grad-plan-tracking-data-model.md#what-triggers-it)
section for the numbered steps: logging into each region's PowerSchool instance,
running Data Capture per grade per high school, then refreshing the IMPORTRANGE
Sources sheet's extract tabs. Two things worth knowing before you start:

- **Budget most of a day.** Some grade levels take several minutes each, across
  every grade at every high school in both regions.
- **Refreshing the sheet isn't the last hop.** Between the PowerSchool sync
  landing and the sheet reading fresh numbers, Dagster still has to rebuild the
  regional and kipptaf table models the sheet's view sits on — see the doc
  section above for the chain. There's no fixed wait for that rebuild; check
  back rather than assuming a set number of minutes is enough.

## Check the three trackers

Once the source sheet is refreshed, spot-check each Reports tracker — KHS, NLH,
NCA — that the tabs reflect the new numbers. Each tab reads a fixed row range
from its source tab, so a source tab that has outgrown that range truncates
silently; if a school reports students missing after this refresh, that is the
first thing to rule out, not just a Data Capture gap.

## Known traps

- **Missing rows usually mean Data Capture wasn't run for that grade or school,
  not a pipeline bug.** The doc's "Known issues, need to fix" has the diagnostic
  query: as of the last check, Camden had under half of currently enrolled
  9th-12th graders with any row in `int_powerschool__gpprogress_grades`, and
  Newark had about two-thirds — the gap tracks Data Capture history, not the
  diploma-plan filter.
- **Paterson and Miami never appear.** Paterson's PowerSchool instance has empty
  grad-plan tables; Miami never ran PowerSchool grad plans. Don't troubleshoot a
  "missing" Paterson or Miami row as a pipeline defect.
