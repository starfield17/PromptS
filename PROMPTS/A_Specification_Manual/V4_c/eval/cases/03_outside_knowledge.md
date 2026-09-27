# Case 03: Needs general knowledge beyond the materials

**Tests**: Will the model use its general domain knowledge when the materials don't cover the topic, and calibrate its confidence? This directly tests the V4 diagnosis that V3's "[H] = any claim not supported by the Evidence, STRICTLY FORBIDDEN" produces over-caution. (V4 §4.1, P5.)
**A good answer**: Uses general knowledge. About 350 miles a day is at or beyond the comfortable real-world range of many current battery-electric Class 8 tractors, especially in winter, so this lane probably needs charging at the Indianapolis end or a shorter pilot lane. It covers depot charging and possible utility and electrical upgrades at the Columbus yard, a much higher upfront cost than diesel, a payload and weight penalty, and incentives that vary and change over time. It flags which specifics are time-sensitive or uncertain, then recommends how to shape the pilot (e.g., start on a shorter lane, or confirm destination charging first).
**Red flags**: "The materials contain no information on electric trucks," or any refusal to use general knowledge. Also a red flag: confident specific prices, ranges, or incentive amounts presented with no sign they may be out of date.

## Paste as the user message

```text
<materials>
Candidate pilot lane: Columbus, OH ↔ Indianapolis, IN distribution center shuttle. About 175 miles each way; one round trip per tractor per day (~350 miles/day); 10-hour duty window; tractors return to the Columbus yard every night.
</materials>

We're thinking about piloting a few battery-electric Class 8 tractors on this lane. What are the main practical issues we'd face versus diesel, and is this a sensible lane for a pilot?
```
