'use client';

import {
  AlertTriangle,
  Box,
  CheckCircle2,
  ChevronLeft,
  CircleStop,
  Download,
  Pause,
  Play,
  RadioTower,
  RotateCcw,
  Route,
  ShieldAlert,
} from 'lucide-react';
import { useEffect, useMemo, useState, type ReactNode } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

type Phase =
  | 'READY'
  | 'EXECUTING'
  | 'SENSOR_DETECTED'
  | 'SAFE_STOP'
  | 'REPLANNING'
  | 'RESUMED'
  | 'COMPLETED';

type Point = { x: number; y: number };

type SimulationEvent = {
  atMs: number;
  kind: string;
  source: string;
  detail: string;
};

const DETECT_AT_MS = 3000;
const ROUTE_A: Point[] = [
  { x: 72, y: 420 },
  { x: 330, y: 420 },
  { x: 620, y: 420 },
  { x: 735, y: 280 },
  { x: 842, y: 135 },
];
const DETOUR_ROUTE: Point[] = [
  { x: 620, y: 420 },
  { x: 620, y: 245 },
  { x: 760, y: 245 },
  { x: 842, y: 135 },
];
const TRAFFIC_LOOP: Point[] = [
  { x: 115, y: 135 },
  { x: 400, y: 135 },
  { x: 500, y: 245 },
  { x: 390, y: 360 },
  { x: 135, y: 360 },
];

const fieldChecklist = [
  'Clock-sync AGV, edge controller, sensor and recorder (≤20 ms skew)',
  'Record one continuous, uncut physical-test video with visible UTC clock',
  'Export raw sensor capture, AGV telemetry and MQTT/VDA 5050 trace',
  'Prove filtered obstacle → stationary AGV ≤200 ms without cloud dependency',
  'Capture changed route version, resumed mission and final x/y/heading pose',
  'Hash all four artifacts and obtain the safety-owner attestation',
];

function schedule(stopLatencyMs: number): SimulationEvent[] {
  const stationaryAt = DETECT_AT_MS + stopLatencyMs;
  return [
    {
      atMs: 0,
      kind: 'mission.started',
      source: 'dispatch.simulator',
      detail: 'AGV-03 accepted route A for P-104',
    },
    {
      atMs: 2900,
      kind: 'sensor.raw_detected',
      source: 'lidar.fixture',
      detail: 'Synthetic return entered the detection envelope',
    },
    {
      atMs: DETECT_AT_MS,
      kind: 'sensor.filtered_obstacle',
      source: 'edge.fixture',
      detail: 'Synthetic obstacle confirmed at N09',
    },
    {
      atMs: DETECT_AT_MS + 12,
      kind: 'edge.stop_issued',
      source: 'edge.fixture',
      detail: 'Local stop command issued; cloud path disabled',
    },
    {
      atMs: stationaryAt,
      kind: 'agv.stationary_confirmed',
      source: 'agv-03.fixture',
      detail: `Synthetic stationary confirmation (${stopLatencyMs} ms)`,
    },
    {
      atMs: stationaryAt + 850,
      kind: 'replan.accepted',
      source: 'planner.fixture',
      detail: 'Route version sim-route-a → sim-route-b',
    },
    {
      atMs: stationaryAt + 1750,
      kind: 'mission.resumed',
      source: 'dispatch.simulator',
      detail: 'AGV-03 resumed on the synthetic detour',
    },
    {
      atMs: stationaryAt + 4700,
      kind: 'mission.completed',
      source: 'agv-03.fixture',
      detail: 'P-104 reached N12; simulated final pose captured',
    },
  ];
}

function phaseAt(
  elapsedMs: number,
  started: boolean,
  stopLatencyMs: number,
): Phase {
  if (!started) return 'READY';
  const stationaryAt = DETECT_AT_MS + stopLatencyMs;
  if (elapsedMs < DETECT_AT_MS) return 'EXECUTING';
  if (elapsedMs < stationaryAt) return 'SENSOR_DETECTED';
  if (elapsedMs < stationaryAt + 850) return 'SAFE_STOP';
  if (elapsedMs < stationaryAt + 1750) return 'REPLANNING';
  if (elapsedMs < stationaryAt + 4700) return 'RESUMED';
  return 'COMPLETED';
}

function pointAlong(points: Point[], progress: number): Point {
  const bounded = Math.max(0, Math.min(1, progress));
  const distances = points
    .slice(1)
    .map((point, index) =>
      Math.hypot(point.x - points[index].x, point.y - points[index].y),
    );
  const total = distances.reduce((sum, distance) => sum + distance, 0);
  let remaining = bounded * total;
  for (let index = 0; index < distances.length; index += 1) {
    if (remaining <= distances[index]) {
      const ratio = distances[index] === 0 ? 0 : remaining / distances[index];
      return {
        x: points[index].x + (points[index + 1].x - points[index].x) * ratio,
        y: points[index].y + (points[index + 1].y - points[index].y) * ratio,
      };
    }
    remaining -= distances[index];
  }
  return points[points.length - 1];
}

function pathData(points: Point[]): string {
  return points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
    .join(' ');
}

function formatElapsed(value: number): string {
  return `${(value / 1000).toFixed(2)} s`;
}

function downloadJson(payload: object): void {
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'hero002-a06-a07-prephysical-rehearsal.json';
  anchor.click();
  URL.revokeObjectURL(url);
}

export function FieldTestSimulator({ onBack }: { onBack: () => void }) {
  const [started, setStarted] = useState(false);
  const [running, setRunning] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [stopLatencyMs, setStopLatencyMs] = useState(150);
  const [mapMode, setMapMode] = useState<'2D' | '3D'>('2D');
  const [sessionStartedAt, setSessionStartedAt] = useState<string | null>(null);

  const events = useMemo(() => schedule(stopLatencyMs), [stopLatencyMs]);
  const completeAtMs = events[events.length - 1].atMs;
  const phase = phaseAt(elapsedMs, started, stopLatencyMs);
  const visibleEvents = events.filter(
    (event) => event.atMs <= elapsedMs && started,
  );

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => {
      setElapsedMs((current) => {
        const next = Math.min(completeAtMs, current + 50 * speed);
        if (next >= completeAtMs) setRunning(false);
        return next;
      });
    }, 50);
    return () => window.clearInterval(timer);
  }, [completeAtMs, running, speed]);

  const heroPosition = useMemo(() => {
    if (elapsedMs <= DETECT_AT_MS) {
      return pointAlong(ROUTE_A.slice(0, 3), elapsedMs / DETECT_AT_MS);
    }
    const resumeAt = DETECT_AT_MS + stopLatencyMs + 1750;
    if (elapsedMs < resumeAt) return ROUTE_A[2];
    return pointAlong(
      DETOUR_ROUTE,
      (elapsedMs - resumeAt) / Math.max(1, completeAtMs - resumeAt),
    );
  }, [completeAtMs, elapsedMs, stopLatencyMs]);

  const startOrPause = () => {
    if (phase === 'COMPLETED') return;
    if (!started) {
      setStarted(true);
      setSessionStartedAt(new Date().toISOString());
    }
    setRunning((current) => !current);
  };

  const reset = () => {
    setRunning(false);
    setStarted(false);
    setElapsedMs(0);
    setSessionStartedAt(null);
  };

  const injectBlockage = () => {
    if (!started) {
      setStarted(true);
      setSessionStartedAt(new Date().toISOString());
    }
    if (elapsedMs < DETECT_AT_MS) setElapsedMs(DETECT_AT_MS);
    setRunning(true);
  };

  const exportRehearsal = () => {
    if (phase !== 'COMPLETED' || !sessionStartedAt) return;
    const baseTime = new Date(sessionStartedAt).getTime();
    downloadJson({
      schema_version: 'prephysical-rehearsal-v1',
      evidence_class: 'simulator_rehearsal',
      claim_scope: 'a06_a07_rehearsal_only',
      final_submission_eligible: false,
      simulator: {
        name: 'ShiftZero A06/A07 Field Test Lab',
        vehicle_count: 9,
        map_mode: mapMode,
        speed_multiplier: speed,
        synthetic_sensor_to_stop_ms: stopLatencyMs,
        cloud_path: 'disabled_in_rehearsal',
      },
      result: {
        rehearsal_completed: true,
        a06_threshold_rehearsed: stopLatencyMs <= 200,
        a06_physical_passed: false,
        a07_physical_passed: false,
        route_version_before: 'sim-route-a',
        route_version_after: 'sim-route-b',
        final_pose: { node_id: 'N12', x: 842, y: 135, heading_deg: 315 },
      },
      events: events.map((event, index) => ({
        sequence: index + 1,
        kind: event.kind,
        source: event.source,
        timestamp: new Date(baseTime + event.atMs).toISOString(),
        elapsed_ms: event.atMs,
        detail: event.detail,
      })),
      limitations: [
        'All sensors, AGVs, timing and motion in this file are synthetic.',
        'This rehearsal cannot satisfy A06 or A07 physical-hardware gates.',
        'Do not upload this file as final physical evidence.',
      ],
      physical_evidence_required: [
        'continuous_video',
        'raw_telemetry',
        'raw_sensor_capture',
        'mqtt_or_vda5050_trace',
        'synchronized_clock_evidence',
        'safety_owner_attestation',
      ],
    });
  };

  return (
    <div className="mx-auto max-w-[1500px] px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-5 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack}
            className="mb-4 -ml-2 text-stone-400 hover:bg-white/[0.04] hover:text-white"
          >
            <ChevronLeft className="size-4" /> Back to Evidence
          </Button>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Badge className="rounded-sm border border-amber-300/30 bg-amber-300/[0.1] font-mono text-[9px] text-amber-200">
              SIMULATOR / PRE-PHYSICAL
            </Badge>
            <Badge className="rounded-sm border border-rose-300/30 bg-rose-300/[0.08] font-mono text-[9px] text-rose-200">
              A06 NOT PASSED
            </Badge>
            <Badge className="rounded-sm border border-rose-300/30 bg-rose-300/[0.08] font-mono text-[9px] text-rose-200">
              A07 NOT PASSED
            </Badge>
          </div>
          <h1 className="text-3xl font-semibold tracking-[-0.03em] text-white sm:text-4xl">
            A06/A07 Field Test Lab
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-stone-400">
            Nine-AGV rehearsal for sensor-stop timing, local safety, blockage
            replan, mission recovery and evidence capture. It prepares the field
            test; only synchronized physical evidence can close the two gates.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={startOrPause}
            disabled={phase === 'COMPLETED'}
            className="rounded-md bg-orange-200 text-[#1b120d] hover:bg-orange-100"
          >
            {running ? (
              <Pause className="size-4" />
            ) : (
              <Play className="size-4" />
            )}
            {running ? 'Pause' : started ? 'Continue' : 'Run rehearsal'}
          </Button>
          <Button
            onClick={injectBlockage}
            disabled={phase === 'COMPLETED' || elapsedMs >= DETECT_AT_MS}
            variant="outline"
            className="rounded-md border-amber-300/25 bg-amber-300/[0.06] text-amber-100 hover:bg-amber-300/[0.12]"
          >
            <ShieldAlert className="size-4" /> Inject blockage
          </Button>
          <Button
            onClick={reset}
            variant="outline"
            className="rounded-md border-white/10 bg-white/[0.03] text-stone-300 hover:bg-white/[0.07]"
          >
            <RotateCcw className="size-4" /> Reset
          </Button>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(330px,0.75fr)]">
        <Card className="overflow-hidden rounded-lg border-white/[0.08] bg-[#22160f] shadow-none">
          <CardHeader className="border-b border-white/[0.07] px-5 py-4">
            <CardTitle className="flex flex-wrap items-center justify-between gap-3 text-xs text-white">
              <span className="flex items-center gap-2">
                <Route className="size-4 text-orange-200" /> Nine-AGV warehouse
                map
              </span>
              <span className="flex items-center gap-2">
                {(['2D', '3D'] as const).map((mode) => (
                  <Button
                    key={mode}
                    size="xs"
                    variant="outline"
                    onClick={() => setMapMode(mode)}
                    className={
                      mapMode === mode
                        ? 'border-orange-200/40 bg-orange-200/10 text-orange-100'
                        : 'border-white/10 bg-transparent text-stone-500'
                    }
                  >
                    {mode}
                  </Button>
                ))}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="grid grid-cols-2 border-b border-white/[0.06] sm:grid-cols-4">
              <SimulatorMetric label="Phase" value={phase} tone="cyan" />
              <SimulatorMetric
                label="Elapsed"
                value={formatElapsed(elapsedMs)}
                tone="slate"
              />
              <SimulatorMetric label="Fleet" value="9 / 9" tone="emerald" />
              <SimulatorMetric
                label="Synthetic stop"
                value={`${stopLatencyMs} ms`}
                tone={stopLatencyMs <= 200 ? 'emerald' : 'rose'}
              />
            </div>
            <div
              className="overflow-hidden bg-[#170f0b] p-3 sm:p-5"
              style={{ perspective: '1200px' }}
            >
              <svg
                viewBox="0 0 920 520"
                aria-label="Functional nine-AGV warehouse simulation map"
                className="w-full transition-transform duration-500"
                style={
                  mapMode === '3D'
                    ? { transform: 'rotateX(48deg) rotateZ(-2deg) scale(0.92)' }
                    : undefined
                }
              >
                <defs>
                  <pattern
                    id="field-grid"
                    width="40"
                    height="40"
                    patternUnits="userSpaceOnUse"
                  >
                    <path
                      d="M 40 0 L 0 0 0 40"
                      fill="none"
                      stroke="#4a3020"
                      strokeWidth="1"
                    />
                  </pattern>
                  <filter
                    id="hero-glow"
                    x="-60%"
                    y="-60%"
                    width="220%"
                    height="220%"
                  >
                    <feGaussianBlur stdDeviation="5" result="blur" />
                    <feMerge>
                      <feMergeNode in="blur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>
                <rect width="920" height="520" fill="url(#field-grid)" />
                {[170, 270, 370, 470, 570, 670].map((x) => (
                  <g key={x}>
                    <rect
                      x={x}
                      y="58"
                      width="58"
                      height="118"
                      rx="4"
                      fill="#342117"
                      stroke="#6d4529"
                    />
                    <rect
                      x={x}
                      y="285"
                      width="58"
                      height="82"
                      rx="4"
                      fill="#342117"
                      stroke="#6d4529"
                    />
                  </g>
                ))}
                <path
                  d={pathData(ROUTE_A)}
                  fill="none"
                  stroke="#7d5030"
                  strokeWidth="12"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d={pathData(ROUTE_A)}
                  fill="none"
                  stroke="#60a5fa"
                  strokeWidth="3"
                  strokeDasharray="10 10"
                />
                {elapsedMs >= DETECT_AT_MS + stopLatencyMs + 850 && (
                  <path
                    d={pathData(DETOUR_ROUTE)}
                    fill="none"
                    stroke="#6ee7b7"
                    strokeWidth="5"
                    strokeDasharray="12 9"
                  />
                )}
                <path
                  d={pathData(TRAFFIC_LOOP)}
                  fill="none"
                  stroke="#583824"
                  strokeWidth="5"
                  strokeDasharray="5 10"
                />

                {[
                  { label: 'N01', point: ROUTE_A[0] },
                  { label: 'N04', point: ROUTE_A[1] },
                  { label: 'N09', point: ROUTE_A[2] },
                  { label: 'N10', point: DETOUR_ROUTE[1] },
                  { label: 'N12', point: ROUTE_A[4] },
                ].map(({ label, point }) => (
                  <g key={label}>
                    <circle
                      cx={point.x}
                      cy={point.y}
                      r="8"
                      fill="#22160f"
                      stroke="#f4bd73"
                      strokeWidth="2"
                    />
                    <text
                      x={point.x}
                      y={point.y - 16}
                      fill="#d0aa7a"
                      fontSize="13"
                      textAnchor="middle"
                    >
                      {label}
                    </text>
                  </g>
                ))}

                {elapsedMs >= DETECT_AT_MS && phase !== 'COMPLETED' && (
                  <g transform="translate(620 420)">
                    <circle r="35" fill="#fb7185" opacity="0.12" />
                    <path
                      d="M -12 -12 L 12 12 M 12 -12 L -12 12"
                      stroke="#fb7185"
                      strokeWidth="7"
                      strokeLinecap="round"
                    />
                    <text
                      x="0"
                      y="54"
                      fill="#fda4af"
                      fontSize="12"
                      textAnchor="middle"
                    >
                      SYNTHETIC BLOCKAGE
                    </text>
                  </g>
                )}

                {Array.from({ length: 8 }, (_, index) => {
                  const position = pointAlong(
                    TRAFFIC_LOOP,
                    (((elapsedMs / 10000 + index / 8) % 1) + 1) % 1,
                  );
                  return (
                    <g
                      key={index}
                      transform={`translate(${position.x} ${position.y})`}
                    >
                      <rect
                        x="-14"
                        y="-9"
                        width="28"
                        height="18"
                        rx="4"
                        fill="#745039"
                        stroke="#d4ad7a"
                      />
                      <text
                        x="0"
                        y="-14"
                        fill="#bf9a70"
                        fontSize="10"
                        textAnchor="middle"
                      >{`AGV-${String(index + (index >= 2 ? 2 : 1)).padStart(2, '0')}`}</text>
                    </g>
                  );
                })}

                <g
                  transform={`translate(${heroPosition.x} ${heroPosition.y})`}
                  filter="url(#hero-glow)"
                >
                  <rect
                    x="-21"
                    y="-14"
                    width="42"
                    height="28"
                    rx="5"
                    fill="#f4bd73"
                    stroke="#ffedd5"
                    strokeWidth="2"
                  />
                  <rect
                    x="-13"
                    y="-8"
                    width="26"
                    height="16"
                    rx="2"
                    fill="#3a2415"
                  />
                  <circle cx="-13" cy="15" r="4" fill="#e2e8f0" />
                  <circle cx="13" cy="15" r="4" fill="#e2e8f0" />
                  <text
                    x="0"
                    y="-22"
                    fill="#ffedd5"
                    fontSize="12"
                    fontWeight="700"
                    textAnchor="middle"
                  >
                    AGV-03 / HERO
                  </text>
                </g>
                <g transform="translate(842 135)">
                  <rect
                    x="20"
                    y="-34"
                    width="42"
                    height="68"
                    rx="4"
                    fill="#3f321b"
                    stroke="#6ee7b7"
                  />
                  <text
                    x="41"
                    y="4"
                    fill="#a7f3d0"
                    fontSize="11"
                    textAnchor="middle"
                  >
                    P-104
                  </text>
                </g>
              </svg>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card className="rounded-lg border-white/[0.08] bg-[#261911] shadow-none">
            <CardHeader className="border-b border-white/[0.07] px-5 py-4">
              <CardTitle className="flex items-center gap-2 text-xs text-white">
                <RadioTower className="size-4 text-orange-200" /> Test controls
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5 p-5">
              <ControlRow label="Playback speed">
                {[1, 2, 4].map((value) => (
                  <Button
                    key={value}
                    size="xs"
                    variant="outline"
                    onClick={() => setSpeed(value)}
                    className={
                      speed === value
                        ? 'border-orange-200/40 bg-orange-200/10 text-orange-100'
                        : 'border-white/10 text-stone-500'
                    }
                  >
                    {value}×
                  </Button>
                ))}
              </ControlRow>
              <ControlRow label="Synthetic sensor → stop">
                {[84, 150, 240].map((value) => (
                  <Button
                    key={value}
                    size="xs"
                    variant="outline"
                    disabled={started}
                    onClick={() => setStopLatencyMs(value)}
                    className={
                      stopLatencyMs === value
                        ? 'border-orange-200/40 bg-orange-200/10 text-orange-100'
                        : 'border-white/10 text-stone-500'
                    }
                  >
                    {value} ms
                  </Button>
                ))}
              </ControlRow>
              <div className="rounded-md border border-white/[0.07] bg-[#1d130e] p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-stone-500">
                    Cloud path
                  </span>
                  <Badge className="rounded-sm bg-emerald-300/10 font-mono text-[8px] text-emerald-200">
                    DISABLED
                  </Badge>
                </div>
                <p className="mt-2 text-[10px] leading-5 text-stone-500">
                  Rehearses a local edge stop. This is a software assertion
                  until the physical network path is disconnected and filmed.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <GateStatus
                  label="A06 rehearsal"
                  passed={phase === 'COMPLETED' && stopLatencyMs <= 200}
                />
                <GateStatus
                  label="A07 rehearsal"
                  passed={phase === 'COMPLETED'}
                />
              </div>
              <Button
                onClick={exportRehearsal}
                disabled={phase !== 'COMPLETED'}
                variant="outline"
                className="w-full rounded-md border-violet-300/25 bg-violet-300/[0.06] text-violet-100 hover:bg-violet-300/[0.12]"
              >
                <Download className="size-4" /> Download rehearsal JSON
              </Button>
            </CardContent>
          </Card>

          <Card className="rounded-lg border-white/[0.08] bg-[#261911] shadow-none">
            <CardHeader className="border-b border-white/[0.07] px-5 py-4">
              <CardTitle className="flex items-center gap-2 text-xs text-white">
                <CircleStop className="size-4 text-rose-200" /> Synthetic event
                timeline
              </CardTitle>
            </CardHeader>
            <CardContent className="max-h-[340px] space-y-2 overflow-y-auto p-4">
              {visibleEvents.length === 0 ? (
                <p className="px-1 py-6 text-center text-xs text-stone-600">
                  Run the rehearsal to emit synthetic events.
                </p>
              ) : (
                visibleEvents.map((event, index) => (
                  <div
                    key={`${event.kind}-${index}`}
                    className="rounded-md border border-white/[0.06] bg-[#1d130e] p-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-mono text-[10px] text-orange-200">
                        {event.kind}
                      </span>
                      <span className="font-mono text-[9px] text-stone-600">
                        +{event.atMs} ms
                      </span>
                    </div>
                    <p className="mt-1 text-[10px] leading-4 text-stone-500">
                      {event.detail}
                    </p>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <Card className="mt-4 rounded-lg border-amber-300/20 bg-amber-300/[0.035] shadow-none">
        <CardHeader className="border-b border-amber-300/10 px-5 py-4">
          <CardTitle className="flex flex-wrap items-center justify-between gap-3 text-xs text-white">
            <span className="flex items-center gap-2">
              <AlertTriangle className="size-4 text-amber-200" /> Physical
              evidence still required
            </span>
            <span className="font-mono text-[9px] text-amber-200">
              FAIL CLOSED UNTIL ONSITE TEST
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 p-5 md:grid-cols-2 xl:grid-cols-3">
          {fieldChecklist.map((item, index) => (
            <div
              key={item}
              className="flex gap-3 rounded-md border border-white/[0.06] bg-[#1d130e] p-3"
            >
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-amber-300/20 font-mono text-[9px] text-amber-200">
                {index + 1}
              </span>
              <p className="text-[11px] leading-5 text-stone-400">{item}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function SimulatorMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'cyan' | 'emerald' | 'rose' | 'slate';
}) {
  const tones = {
    cyan: 'text-orange-200',
    emerald: 'text-emerald-200',
    rose: 'text-rose-200',
    slate: 'text-stone-200',
  };
  return (
    <div className="border-r border-white/[0.06] px-4 py-3 last:border-r-0">
      <p className="font-mono text-[8px] uppercase tracking-[0.14em] text-stone-600">
        {label}
      </p>
      <p className={`mt-1 font-mono text-xs font-semibold ${tones[tone]}`}>
        {value}
      </p>
    </div>
  );
}

function ControlRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <p className="mb-2 font-mono text-[9px] uppercase tracking-[0.14em] text-stone-500">
        {label}
      </p>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

function GateStatus({ label, passed }: { label: string; passed: boolean }) {
  return (
    <div
      className={`rounded-md border p-3 ${passed ? 'border-emerald-300/20 bg-emerald-300/[0.05]' : 'border-white/[0.07] bg-[#1d130e]'}`}
    >
      <div className="flex items-center gap-2">
        {passed ? (
          <CheckCircle2 className="size-4 text-emerald-300" />
        ) : (
          <Box className="size-4 text-stone-600" />
        )}
        <span
          className={`font-mono text-[9px] ${passed ? 'text-emerald-200' : 'text-stone-500'}`}
        >
          {label}
        </span>
      </div>
      <p className="mt-2 text-[9px] text-stone-600">
        {passed ? 'SIMULATION PASS' : 'NOT RUN'}
      </p>
    </div>
  );
}
