# Do SMS reminders reduce no-shows?

**Short answer: yes, by about 5.4 percentage points for appointments booked 3+ days ahead. But the raw data says the opposite.**

## 1. The naive comparison (misleading)

| | No-show rate |
|---|---|
| Got an SMS reminder | 27.6% |
| No reminder | 16.7% |

Taken at face value, reminders look like they *increase* no-shows.

## 2. Why: booking lead time

Reminders were only sent for appointments booked 3+ days ahead. Same-day
appointments almost never get missed, and none of them got a reminder. So the
"no reminder" group is full of easy, same-day visits. That's confounding.

Comparing within the same booking window (no-show rate, with appointment count):

| Booked ahead | With SMS | Without SMS |
|---|---|---|
| Same day | — (0) | 4.7% (38,518) |
| 1-2 days | — (0) | 22.7% (11,924) |
| 3-7 days | 23.8% (11,535) | 26.6% (8,688) |
| 8-14 days | 28.1% (6,992) | 33.8% (5,012) |
| 15-30 days | 29.8% (10,501) | 36.8% (6,839) |
| 31+ days | 30.2% (6,402) | 37.5% (3,965) |

In **every** window where both groups exist, reminded patients miss fewer appointments.

## 3. Adjusted estimate

Logistic regression on appointments booked 3+ days ahead (59,934 appointments),
controlling for lead-time window, age group and sex:

- **Odds ratio for SMS: 0.77** (95% CI 0.74–0.79, p < 0.001)
- **Average effect: -5.4 percentage points** in no-show probability

## 4. Caveats

- **Observational, not an experiment.** Who got a reminder wasn't random within a
  window. Unmeasured factors (e.g. having a valid phone number) could still bias this.
  The right next step is an A/B test: randomly withhold reminders for a small share.
- Data is from one city's public clinics in 2016.
- Unmapped visit statuses (LWBS, blank, "?") and 5 rows booked after the visit
  date are excluded.

## Recommendation

Keep sending reminders, and test whether reminders for 1–2 day bookings (currently
never sent) reduce no-shows there too. That window has a 23% no-show rate and no reminders.
