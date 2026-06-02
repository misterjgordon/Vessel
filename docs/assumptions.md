# Financial Assumptions

Key assumptions underpinning the DCF model. These follow standard corporate finance conventions for long-lived asset valuation.

---

## Timing

- All cash flows occur at the **end of each year** (31 December convention).
- Year 0 is the purchase year. The vessel purchase price is a full outflow at end of Year 0.
- Operating cash flows begin in Year 1 and run through Year T (vessel life).
- Residual value (sale or scrap proceeds) is received at the end of Year T only, added to that year's operating cash flow.

## Revenue

- Revenue is **fixed** for the life of the vessel. It does not inflate.
- This reflects a time-charter contract where the daily rate is locked at signing.
- Not a bareboat charter: the owner bears OpEx and CapEx; the charterer does not operate the vessel in this model.
- Off-hire reduces effective revenue days. During off-hire periods the vessel earns nothing but still incurs full OpEx.
- **Inflation** escalates OpEx and CapEx only, not revenue: the charter rate is fixed for the contract term, so general inflation does not increase hire income in this model.

## Costs

- **OpEx** (operating expense per day) inflates annually at the stated inflation rate from Year 1 onward.
- **CapEx** (drydock and upgrades) also inflates annually at the same rate.
- Inflation is applied as a compounding factor: `(1 + inflation_rate) ^ t` where `t` is the year number.

## Drydock

- Drydock occurs every 5 years by default (configurable via `drydock_frequency`).
- Under a 25-year vessel life with 5-year frequency, drydock years are: 5, 10, 15, 20.
- Year 25 is not a drydock year — the vessel reaches end of life before the next cycle.

## Vessel Life

- Default vessel life is **25 years**.
- This is consistent with the reference model and industry convention for container vessels of this class.

## No Early Exit

- There is no buyout or early sale option modelled.
- The vessel is assumed to operate for its full expected life. The only terminal cash flow is the residual value at Year T.
- This is a simplifying assumption for the prototype. A production model could add optional early-exit scenarios.

## Discount Rate

- The discount rate represents the company's required return on investment (also called the hurdle rate).
- It is applied uniformly across all years. No term structure is modelled.
- **IRR** is solved on the same unlevered net cashflows as NPV: Year 0 is the full purchase price as a cash outflow; there is no debt, interest, or levered equity return.

## Breakeven charter rate

- Breakeven is the **gross** revenue per day (contract / time-charter rate) at which NPV equals zero, holding all other inputs fixed—including the entered **off-hire rate**.
- It is **not** the effective daily rate after off-hire; effective revenue in the model is `revenue_per_day × (1 − offhire_rate)`.
- Breakeven uses the same discount rate as the base-case NPV, not scenario overrides.

## Sensitivity Analysis

- The sensitivity chart shows IRR at each $1,000 increment of Revenue per Day between a user-defined minimum and maximum.
- Default range is the entered Revenue per Day ± $5,000. The user can widen or narrow this.
- The $1,000 step size is fixed per the case study requirement.

## Scenario Analysis

- Scenarios apply to inflation rate and discount rate together as paired bundles (Best/Base/Worst).
- Pairing is required because the discount rate contains inflation expectations — separating them produces economically inconsistent scenarios (see Fisher equation).
- Default **discount rates** for Best / Base / Worst are **8%**, **10%**, and **12%**, each paired with inflation **1%**, **3%**, and **5%** — Fisher-style bundles so macro stress moves nominal rates together rather than mixing unrelated inflation and hurdle assumptions.
- Across those defaults, the **real** required return (hurdle above inflation) is held at **2%** for Best, Base, and Worst; the **Base** pair (3% inflation, 10% discount) matches the case-study reference inputs and golden tests.
- In each default bundle, the **nominal** gap between discount rate and inflation is **7 percentage points** (e.g. 10% − 3%); that pairing comes from the case-study test data, not from a separate policy knob in the app.
- Users may override individual values within a bundle; the tool warns but does not block inconsistent pairs.
- The Base scenario always matches the originally entered assumptions. It is the default view.

## Purchase Price Validation

- TEU size is a required input. It is the primary dimension for comparing vessel values across the fleet.
- For Tier 2 checks, TEU is rounded to the **nearest 1,000** (e.g. 7,460 → 7,000) before lookup in purchase-price and revenue benchmarks.
- **Save to database** rejects duplicates: the same `vessel_name`, `purchase_date`, and `teu_size` cannot be saved twice (case-insensitive name). Load the existing entry or change identity fields.
- A vessel's purchase price is cross-checked against the **median** purchase price of other vessels in the same TEU class. Median is used rather than mean because it is robust to outliers in small samples.
- A value outside ±10% of the TEU-class median triggers a Tier 2 warning.
- On first upload, the median is computed from valid rows within the same batch (Tier 1 error rows are excluded before the median is calculated).
- Tier 2 warnings on batch uploads are correctable inline — the user edits the flagged value directly in the results table without re-uploading the file.
- The ±10% threshold is a starting assumption based on the available sample data and should be calibrated against real fleet transaction data in production.

## Revenue per Day — Normal Range

- Revenue-per-day checks use a fixed ±$5,000 dollar band around a seeded anchor—not a percentage.
- Expected revenue per day varies by vessel size (TEU capacity). Anchors derived from sample data (TEU rounded to the nearest 1,000 before lookup):

  | TEU class | Anchor rate |
  |-----------|-------------|
  | 7,000 TEU | ~$40,000/day |
  | 8,000 TEU | ~$45,000/day |
  | 10,000 TEU | ~$50,000/day |
  | 12,000 TEU | ~$54,000/day |

- A Tier 2 warning fires when `|entered rate − anchor| > $5,000`—symmetric above and below. Exactly $5,000 away from the anchor does not warn (e.g. $45,000/day or $55,000/day for a $50,000 anchor); $44,999/day or $55,001/day does.
- Effective daily revenue (after off-hire) below OpEx per day triggers a separate Tier 2 warning; that check is independent of the TEU anchor band.
- These anchors are stubs based on 10 sample vessels and will need updating with real market data in production.

## Residual Value

- Residual value represents the proceeds from selling or scrapping the vessel at end of life.
- It is expressed in nominal terms (not inflation-adjusted) and treated as a fixed contractual estimate.
