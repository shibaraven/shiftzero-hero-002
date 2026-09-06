# Three-minute demo video shot list

Encoded target: 2:58. The uploaded file must remain below three minutes after the final encode.
This is the official no-hardware Physical AI version: Devpost permits entries without hardware to
show the key application modules in action. Keep `DIGITAL TWIN / SIMULATION` visible whenever the
simulator is shown. Capture only after the public URL, repository revision and real-provider
evidence are frozen.

## 0:00-0:15 - Problem, solution and result

- Open on the moving nine-AGV Digital Twin and the title: “One sentence in. One verified robot
  mission out.”
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

## 0:58-2:03 - Continuous Digital Twin key-module sequence

Continuous key-module simulation segment: 65 seconds. Use one uninterrupted screen recording of
the Digital Twin Lab. Do not hide the simulation label, correlation ID, synthetic timing label or
cloud state.

- Show AGV-03 begin simulated motion with `missionId`, `sessionId` and `traceId` correlated.
- Show `network.cloud_disconnected` occur before the synthetic obstacle is injected.
- Keep recording through filtered sensor detection, local stop, stationary confirmation at 150 ms,
  verified replan, resume and arrival at `RACK-A12`.
- Show route version `sim-route-a` change to `sim-route-b` and the final `x/y/heading` pose.
- Do not cut or hide labels inside this 65-second segment.

## 2:03-2:31 - Measured evidence

- Show synthetic sensor-to-stop latency, Token Factory latency/tokens/cost and sample sizes. Say
  explicitly that the 150 ms number is simulation timing, not a physical measurement.
- Show the 100-scenario result and 20-run Hero reliability report with their simulator scope labels.
- Show the Evidence Bundle hash and distinguish live-provider evidence from simulator evidence.

## 2:31-2:53 - Product and impact

- Explain Project -> IP -> Product -> License/OEM.
- Present the 400-500 pallets/day model as a planning projection unless physical throughput has
  been measured under the declared method.
- Show the anonymous public Judge Mode and immutable public repository URL.

## 2:53-2:58 - Close

- Return to the completed Digital Twin mission and final pose.
- Close with: “AI proposes. Rules authorize. Humans remain accountable.”

## Required capture checklist

- [ ] Encoded duration is no more than 2:58 and resolution is at least 1080p.
- [ ] English narration and burned-in English subtitles are present.
- [ ] The first 15 seconds state the problem, solution and result.
- [ ] Architecture explanation is no longer than 20 seconds.
- [ ] The 65-second key-module simulation segment is continuous and includes cloud disconnect,
      motion, blockage, local stop, replan, resume and completion.
- [ ] `DIGITAL TWIN / SIMULATION` and `NO PHYSICAL CLAIM` remain visible.
- [ ] The shared correlation ID aligns the sensor, edge, vehicle and mission events.
- [ ] Public URL works in an anonymous/private window and on a mobile network.
- [ ] No secrets, local usernames, private endpoints, customer data or unauthorized marks appear.
- [ ] No unlicensed music or third-party media is used.
- [ ] Live Nebius footage is captured only after the official Compatibility Gate passes.
- [ ] Every numeric claim matches its evidence artifact, sample size and method.
