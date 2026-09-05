# Three-minute demo video shot list

Encoded target: 2:58. The uploaded file must remain below three minutes after the final encode.
Capture only after the public URL, repository revision, real-provider evidence and physical test
window are frozen.

## 0:00-0:15 - Problem, solution and result

- Open on the physical AGV and the title: “One sentence in. One verified robot mission out.”
- State the risk, solution and visible result within the first 15 seconds: an LLM must not directly
  actuate a warehouse robot; ShiftZero verifies and authorizes a completed mission.
- Do not spend these seconds on team introductions or architecture.

## 0:15-0:35 - Five-layer architecture and live provider

- Show the five-layer architecture for no more than 20 seconds.
- Show the real `nebius_token_factory` provider, exact Nemotron model ID and a redacted request ID.
- Say: “Nemotron proposes. Deterministic systems authorize motion.”

## 0:35-0:58 - Intent to verified proposal

- Enter the hero intent: move `P-104` from `INBOUND-01` to `RACK-A12`.
- Show real typed calls, Proposal, Safety Proof and human Approve.
- Keep the real-provider receipt and schema-valid result visible without exposing the API key.

## 0:58-2:03 - Continuous physical AGV sequence

Continuous physical segment: 65 seconds. Use one uninterrupted physical-camera take; PiP may show
the synchronized Command Center and real trace but must not replace or obscure the hardware view.

- Show AGV-03 begin physical motion with `missionId`, `orderId` and `traceId` correlated.
- Introduce the aisle obstruction from a controlled safe distance.
- Keep the camera rolling through the sensor event, local stop, visible stop timestamp, verified
  replan, resume and arrival at `RACK-A12`.
- The local safety owner must retain emergency-stop authority throughout the take.
- Do not cut, time-compress or substitute simulator footage inside this 65-second segment.

## 2:03-2:31 - Measured evidence

- Show measured physical sensor-to-stop latency, Token Factory latency/tokens/cost and sample sizes.
- Show the 100-scenario result and 20-run Hero reliability report with their simulator scope labels.
- Show the Evidence Bundle hash and distinguish physical, live-provider and simulator evidence.

## 2:31-2:53 - Product and impact

- Explain Project -> IP -> Product -> License/OEM.
- Present the 400-500 pallets/day model as a planning projection unless physical throughput has
  been measured under the declared method.
- Show the anonymous public Judge Mode and immutable public repository URL.

## 2:53-2:58 - Close

- Return to the completed physical mission and final pose.
- Close with: “AI proposes. Rules authorize. Humans remain accountable.”

## Required capture checklist

- [ ] Encoded duration is no more than 2:58 and resolution is at least 1080p.
- [ ] English narration and burned-in English subtitles are present.
- [ ] The first 15 seconds state the problem, solution and result.
- [ ] Architecture explanation is no longer than 20 seconds.
- [ ] The 65-second physical segment is continuous and includes motion, blockage, local stop,
      replan, resume and completion.
- [ ] PiP timestamps align the hardware, sensor event and real trace.
- [ ] Public URL works in an anonymous/private window and on a mobile network.
- [ ] No secrets, local usernames, private endpoints, customer data or unauthorized marks appear.
- [ ] No unlicensed music or third-party media is used.
- [ ] Live Nebius footage is captured only after the official Compatibility Gate passes.
- [ ] Every numeric claim matches its evidence artifact, sample size and method.
