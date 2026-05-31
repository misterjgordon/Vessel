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
- Off-hire reduces effective revenue days. During off-hire periods the vessel earns nothing but still incurs full OpEx.

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

## Sensitivity Analysis

- The sensitivity chart shows IRR at each $1,000 increment of Revenue per Day between a user-defined minimum and maximum.
- Default range is the entered Revenue per Day ± $5,000. The user can widen or narrow this.
- The $1,000 step size is fixed per the case study requirement.

## Scenario Analysis

- Scenarios apply to inflation rate and discount rate together as paired bundles (Best/Base/Worst).
- Pairing is required because the discount rate contains inflation expectations — separating them produces economically inconsistent scenarios (see Fisher equation).
- Default bundles hold the real required return (discount rate minus inflation) constant at 2% across all scenarios.
- Users may override individual values within a bundle; the tool warns but does not block inconsistent pairs.
- The Base scenario always matches the originally entered assumptions. It is the default view.

## Purchase Price Validation

- TEU size is a required input. It is the primary dimension for comparing vessel values across the fleet.
- A vessel's purchase price is cross-checked against the **median** purchase price of other vessels in the same TEU class. Median is used rather than mean because it is robust to outliers in small samples.
- A value outside ±10% of the TEU-class median triggers a Tier 2 warning.
- On first upload, the median is computed from valid rows within the same batch (Tier 1 error rows are excluded before the median is calculated).
- Tier 2 warnings on batch uploads are correctable inline — the user edits the flagged value directly in the results table without re-uploading the file.
- The ±10% threshold is a starting assumption based on the available sample data and should be calibrated against real fleet transaction data in production.

## Revenue per Day — Normal Range

- Expected revenue per day varies by vessel size (TEU capacity). Benchmarks derived from sample data:

  | TEU class | Expected range |
  |-----------|----------------|
  | 7,000 TEU | ~$40,000/day |
  | 8,000 TEU | ~$45,000/day |
  | 10,000 TEU | ~$50,000/day |
  | 12,000 TEU | ~$54,000/day |

- A value more than $5,000 outside the expected range for the vessel's TEU class triggers a Tier 2 warning.
- These benchmarks are stubs based on 10 sample vessels and will need updating with real market data in production.

## Residual Value

- Residual value represents the proceeds from selling or scrapping the vessel at end of life.
- It is expressed in nominal terms (not inflation-adjusted) and treated as a fixed contractual estimate.
