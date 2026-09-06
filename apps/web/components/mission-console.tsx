'use client';

import {
  Activity,
  AlertTriangle,
  Check,
  ChevronRight,
  CircleStop,
  Cpu,
  Download,
  FileCheck2,
  Fingerprint,
  GitBranch,
  KeyRound,
  Layers3,
  LockKeyhole,
  MapPinned,
  Play,
  RadioTower,
  RotateCcw,
  Route,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  Zap,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

type View = 'mission' | 'architecture' | 'evidence' | 'source';
type ReplayDecision = 'approved' | 'rejected' | 'stopped' | null;

type HeroSummary = {
  evidence_captured_at: string;
  proposal_id: string;
  selected_agv: string;
  safety_policy_sha256: string;
  safety_checks: Array<{
    name: string;
    passed: boolean;
    detail: string;
    evidence_hash: string;
  }>;
  stop_latency_ms: number;
  stop_latency_kind: string;
  trace_chain_valid: boolean;
  trace_id: string;
  total_duration_ms?: number;
  human_interventions?: number;
  estimated_model_cost_usd?: number;
  operation_metrics?: {
    schema_version: string;
    mission_id: string;
    sample_size: number;
    completed: boolean;
    total_duration_ms: number;
    human_interventions: number;
  };
  final_node: string;
  destination_occupancy: string;
  final_pose: {
    node_id: string;
    x: number;
    y: number;
    heading_deg: number;
  };
  model_calls?: Array<{
    provider: string;
    model: string;
    request_id: string;
    tool_name: string;
    latency_ms: number;
    tool_arguments_hash: string;
    tool_result_hash: string;
  }>;
};

type JudgeLoadEvidence = {
  measurement_scope: string;
  sample_count: number;
  median_ms: number;
  p95_ms: number;
  threshold_ms: number;
  acceptance_passed: boolean;
  measured_at: string;
};

type ImpactLoadModel = {
  measurement_scope: string;
  assumptions_are_not_measurements: boolean;
  loads: Array<{
    pallets_per_day: number;
    agv_metrics: {
      mean_utilization: number;
      p95_queue_wait_seconds: number;
      required_agvs_for_80_percent_buffer: number;
      status: string;
    };
    operator_impact: {
      hours_saved_per_day: number;
      touch_time_reduction_percent: number;
    };
  }>;
};

type ScenarioMetrics = {
  sample_size: number;
  validated_count: number;
  safety_violation_count: number;
  unsafe_plan_rejection_recall: number;
};

type ScreenshotEvidence = {
  evidence_class: string;
  final_submission_eligible: boolean;
  real_provider: boolean;
  replacement_required_after_live_gate: boolean;
};

type LiveGateEvidence = {
  generated_at: string;
  provider: string;
  model: string;
  real_provider: boolean;
  official_gate_passed: boolean;
  all_thresholds_passed: boolean;
  report_hash: string;
  failures: Array<string>;
  metrics: {
    requested_runs: number;
    completed_runs: number;
    first_schema_valid_rate: number;
    post_repair_schema_valid_rate: number;
    hero_max_consecutive_successes: number;
    intent_to_proposal_p95_seconds: number;
  };
};

const views: Array<{ id: View; label: string }> = [
  { id: 'mission', label: 'Run Hero' },
  { id: 'architecture', label: 'Architecture' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'source', label: 'GitHub' },
];

const timeline = [
  {
    state: 'INTENT',
    event: 'intent.received',
    detail: 'Move pallet P-104 from INBOUND-01 to RACK-A12',
    tone: 'cyan',
  },
  {
    state: 'OBSERVED',
    event: 'get_operational_snapshot',
    detail: 'Map, robot, zones and inventory resolved',
    tone: 'slate',
  },
  {
    state: 'PLANNED',
    event: 'plan_transport',
    detail: 'AGV-03 selected · route A calculated',
    tone: 'violet',
  },
  {
    state: 'PROPOSED',
    event: 'propose_transport',
    detail: 'Typed proposal ready for review',
    tone: 'slate',
  },
  {
    state: 'VERIFIED',
    event: 'safety.proof',
    detail: '11 route, policy and approval-integrity checks passed',
    tone: 'emerald',
  },
  {
    state: 'APPROVED',
    event: 'approval.granted',
    detail: 'Human approval bound to proposal hash',
    tone: 'emerald',
  },
  {
    state: 'EXECUTING',
    event: 'mission.started',
    detail: 'Simulator accepted signed command',
    tone: 'cyan',
  },
  {
    state: 'EXECUTING',
    event: 'get_mission_status',
    detail: 'Typed mission status and telemetry read recorded',
    tone: 'slate',
  },
  {
    state: 'BLOCKED',
    event: 'sensor.aisle_blocked',
    detail: 'Unexpected obstacle at node N09',
    tone: 'amber',
  },
  {
    state: 'SAFE_STOP',
    event: 'execution.local_stop',
    detail: 'Local simulator stop measured and written to trace',
    tone: 'rose',
  },
  {
    state: 'SAFE_STOP',
    event: 'recovery.intent',
    detail: 'Typed recovery preserves the approved goal',
    tone: 'violet',
  },
  {
    state: 'REPLANNING',
    event: 'replan_mission',
    detail: 'Route B avoids the blocked aisle',
    tone: 'violet',
  },
  {
    state: 'VERIFIED',
    event: 'safety.replan_proof',
    detail: 'Replacement route independently verified',
    tone: 'emerald',
  },
  {
    state: 'EXECUTING',
    event: 'execution.resumed',
    detail: 'Approved recovery policy resumed motion',
    tone: 'cyan',
  },
  {
    state: 'COMPLETED',
    event: 'outcome.completed',
    detail: 'P-104 delivered at RACK-A12 · proof sealed',
    tone: 'emerald',
  },
] as const;

const suites = [
  ['S01', 'Nominal transport', 20, '#67e8e3'],
  ['S02', 'Aisle blockage', 20, '#a69cff'],
  ['S03', 'Low battery', 15, '#f5c563'],
  ['S04', 'Destination occupied', 15, '#67dba5'],
  ['S05', 'Reservation conflict', 15, '#5eb7ff'],
  ['S06', 'Ambiguous intent', 15, '#ff8a9a'],
] as const;

const architectureLayers = [
  {
    number: '01',
    title: 'Language & orchestration',
    detail:
      'Nemotron emits typed tool calls; it never commands robot motion directly.',
    icon: Sparkles,
    label: 'ADVISORY',
  },
  {
    number: '02',
    title: 'Deterministic safety kernel',
    detail:
      'Frozen rules validate state, route, zones, battery, payload and approval binding.',
    icon: ShieldCheck,
    label: 'AUTHORITATIVE',
  },
  {
    number: '03',
    title: 'Mission state machine',
    detail:
      'Every transition is explicit, allow-listed and written to an append-only trace.',
    icon: GitBranch,
    label: 'AUTHORITATIVE',
  },
  {
    number: '04',
    title: 'Adapter boundary',
    detail:
      'Reference simulator today; physical AGV remains gated behind a safety-approved hardware handoff.',
    icon: Layers3,
    label: 'SWAPPABLE',
  },
  {
    number: '05',
    title: 'Local edge stop',
    detail:
      'The robot-side controller can stop without waiting for an LLM or network round trip.',
    icon: CircleStop,
    label: 'LOCAL',
  },
] as const;

function classNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(' ');
}

function StatusDot({ tone = 'cyan' }: { tone?: string }) {
  return <span className={`status-dot status-${tone}`} aria-hidden="true" />;
}

function DataPill({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded border border-white/10 bg-white/[0.035] px-2 py-1 font-mono text-[10px] tracking-[0.08em] text-slate-400">
      {children}
    </span>
  );
}

export default function MissionConsole() {
  const [view, setView] = useState<View>('mission');
  const [runStep, setRunStep] = useState(timeline.length - 1);
  const [running, setRunning] = useState(false);
  const [decision, setDecision] = useState<ReplayDecision>(null);
  const [heroSummary, setHeroSummary] = useState<HeroSummary | null>(null);
  const [scenarioMetrics, setScenarioMetrics] =
    useState<ScenarioMetrics | null>(null);
  const [evidenceError, setEvidenceError] = useState(false);
  const [judgeLoad, setJudgeLoad] = useState<JudgeLoadEvidence | null>(null);
  const [impactLoad, setImpactLoad] = useState<ImpactLoadModel | null>(null);
  const [screenshotEvidence, setScreenshotEvidence] =
    useState<ScreenshotEvidence | null>(null);
  const [liveGate, setLiveGate] = useState<LiveGateEvidence | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetch('/data/hero-summary.json')
      .then((response) => {
        if (!response.ok) throw new Error('hero evidence unavailable');
        return response.json() as Promise<HeroSummary>;
      })
      .then(setHeroSummary)
      .catch(() => setEvidenceError(true));
    fetch('/data/metrics.json')
      .then((response) => {
        if (!response.ok) throw new Error('scenario evidence unavailable');
        return response.json() as Promise<ScenarioMetrics>;
      })
      .then(setScenarioMetrics)
      .catch(() => setEvidenceError(true));
    fetch('/data/judge-mode-load.json')
      .then((response) => {
        if (!response.ok) throw new Error('Judge Mode load evidence unavailable');
        return response.json() as Promise<JudgeLoadEvidence>;
      })
      .then(setJudgeLoad)
      .catch(() => setEvidenceError(true));
    fetch('/data/impact-load-model.json')
      .then((response) => {
        if (!response.ok) throw new Error('impact load model unavailable');
        return response.json() as Promise<ImpactLoadModel>;
      })
      .then(setImpactLoad)
      .catch(() => setEvidenceError(true));
    fetch('/data/screenshot-manifest.json')
      .then((response) => {
        if (!response.ok) throw new Error('screenshot evidence unavailable');
        return response.json() as Promise<ScreenshotEvidence>;
      })
      .then(setScreenshotEvidence)
      .catch(() => setEvidenceError(true));
    fetch('/data/live-gate.json')
      .then((response) => {
        if (!response.ok) throw new Error('live gate evidence unavailable');
        return response.json() as Promise<LiveGateEvidence>;
      })
      .then(setLiveGate)
      .catch(() => setEvidenceError(true));
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const runHero = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setView('mission');
    setRunStep(0);
    setRunning(true);
    setDecision(null);
    let next = 0;
    timerRef.current = setInterval(() => {
      next += 1;
      setRunStep(next);
      if (next >= timeline.length - 1) {
        if (timerRef.current) clearInterval(timerRef.current);
        setRunning(false);
      }
    }, 620);
  };

  const replayControl = (nextDecision: Exclude<ReplayDecision, null>) => {
    if (timerRef.current) clearInterval(timerRef.current);
    setRunning(false);
    setDecision(nextDecision);
    setRunStep(
      nextDecision === 'approved'
        ? timeline.findIndex((item) => item.state === 'APPROVED')
        : nextDecision === 'stopped'
          ? timeline.findIndex((item) => item.event === 'execution.local_stop')
          : timeline.findIndex((item) => item.state === 'VERIFIED'),
    );
  };

  const active = timeline[Math.min(runStep, timeline.length - 1)];
  const blocked =
    runStep >= timeline.findIndex((item) => item.state === 'BLOCKED');
  const replanned =
    runStep >= timeline.findIndex((item) => item.event === 'replan_mission');
  const complete = runStep >= timeline.length - 1;

  return (
    <main className="min-h-screen bg-[#07111f] text-slate-100">
      <div className="pointer-events-none fixed bottom-3 right-3 z-[70] rounded border border-amber-300/25 bg-[#07111f]/95 px-2.5 py-1.5 font-mono text-[8px] tracking-[0.08em] text-amber-100 shadow-xl backdrop-blur">
        <span className="font-bold">MOCK / FIXTURE</span>
        <span className="mx-1.5 text-slate-600">·</span>
        <time dateTime={heroSummary?.evidence_captured_at}>
          EVIDENCE UTC {heroSummary?.evidence_captured_at ?? 'LOADING'}
        </time>
      </div>
      <header className="sticky top-0 z-50 border-b border-white/[0.08] bg-[#07111f]/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1500px] items-center justify-between px-4 sm:px-6 lg:px-8">
          <button
            className="group flex items-center gap-3"
            onClick={() => setView('mission')}
          >
            <span className="grid size-9 place-items-center rounded-md border border-cyan-300/30 bg-cyan-300/10 text-cyan-200 shadow-[0_0_22px_rgba(103,232,227,.12)]">
              <Route className="size-5" />
            </span>
            <span className="text-left">
              <span className="block text-[15px] font-bold tracking-[0.16em] text-white">
                SHIFTZERO
              </span>
              <span className="block font-mono text-[9px] tracking-[0.22em] text-slate-500">
                HERO—002 / JUDGE MODE
              </span>
            </span>
          </button>

          <nav
            className="hidden items-center gap-1 md:flex"
            aria-label="Primary navigation"
          >
            {views.map((item) => (
              <Button
                key={item.id}
                variant="ghost"
                size="sm"
                onClick={() => setView(item.id)}
                className={classNames(
                  'h-9 rounded-md px-4 text-xs capitalize tracking-wide',
                  view === item.id
                    ? 'bg-white/[0.07] text-white'
                    : 'text-slate-400 hover:bg-white/[0.04] hover:text-white',
                )}
              >
                {item.label}
              </Button>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <Button
              onClick={() => setView('source')}
              title="Inspect source readiness and publication gate"
              variant="ghost"
              size="sm"
              className="hidden h-8 rounded-md px-3 font-mono text-[9px] text-slate-500 lg:flex"
            >
              <GitBranch className="size-3" /> SOURCE GATE
            </Button>
            <Badge
              variant="outline"
              className={classNames(
                'hidden h-8 rounded-md px-3 font-mono text-[9px] tracking-[0.12em] sm:flex',
                liveGate?.official_gate_passed
                  ? 'border-emerald-300/20 bg-emerald-300/[0.06] text-emerald-200'
                  : 'border-amber-300/20 bg-amber-300/[0.06] text-amber-200',
              )}
            >
              {liveGate?.official_gate_passed ? (
                <ShieldCheck className="size-3" />
              ) : (
                <LockKeyhole className="size-3" />
              )}
              {liveGate?.official_gate_passed
                ? 'LIVE GATE PASSED'
                : 'LIVE GATE VERIFYING'}
            </Badge>
            <Badge className="hidden h-8 rounded-md border border-rose-300/25 bg-rose-300/[0.08] px-3 font-mono text-[9px] tracking-[0.12em] text-rose-200 sm:flex">
              MOCK / FIXTURE
            </Badge>
            <Button
              onClick={runHero}
              disabled={running}
              size="sm"
              className="h-9 rounded-md bg-cyan-200 px-4 text-xs font-bold text-[#07111f] hover:bg-cyan-100"
            >
              {running ? (
                <Activity className="size-3.5 animate-pulse" />
              ) : (
                <Play className="size-3.5 fill-current" />
              )}
              {running ? 'RUNNING' : 'RUN HERO'}
            </Button>
          </div>
        </div>
      </header>

      <section className="border-b border-white/[0.06] bg-[#091626]">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-3 px-4 py-2.5 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <StatusDot tone="emerald" />
            <span className="font-medium text-slate-200">MOCK verified replay</span>
            <span className="text-slate-700">/</span>
            <span>
              Reference simulator · deterministic fixture · no cloud key loaded
              in Judge Mode
            </span>
          </div>
          <div className="flex items-center gap-2">
            <DataPill>SCHEMA v2</DataPill>
            <DataPill>
              POLICY sha256:
              {heroSummary?.safety_policy_sha256.slice(0, 8) ?? 'loading'}…
            </DataPill>
            <DataPill>
              {evidenceError
                ? 'EVIDENCE LOAD ERROR'
                : heroSummary?.trace_chain_valid
                  ? 'TRACE CHAIN VALID'
                  : 'VERIFYING TRACE'}
            </DataPill>
          </div>
        </div>
      </section>

      <div className="md:hidden">
        <div className="grid grid-cols-4 border-b border-white/[0.06]">
          {views.map((item) => (
            <button
              key={item.id}
              onClick={() => setView(item.id)}
              className={classNames(
                'py-3 text-[10px] font-bold uppercase tracking-[0.15em]',
                view === item.id
                  ? 'border-b border-cyan-200 text-cyan-200'
                  : 'text-slate-500',
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {view === 'mission' && (
        <MissionView
          active={active}
          blocked={blocked}
          complete={complete}
          replanned={replanned}
          runStep={runStep}
          running={running}
          decision={decision}
          heroSummary={heroSummary}
          onControl={replayControl}
          onRun={runHero}
        />
      )}
      {view === 'architecture' && <ArchitectureView onRun={runHero} />}
      {view === 'evidence' && (
        <EvidenceView
          heroSummary={heroSummary}
          scenarioMetrics={scenarioMetrics}
          judgeLoad={judgeLoad}
          impactLoad={impactLoad}
          screenshotEvidence={screenshotEvidence}
          liveGate={liveGate}
          evidenceError={evidenceError}
        />
      )}
      {view === 'source' && <SourceView />}
    </main>
  );
}

function MissionView({
  active,
  blocked,
  complete,
  replanned,
  runStep,
  running,
  decision,
  heroSummary,
  onControl,
  onRun,
}: {
  active: (typeof timeline)[number];
  blocked: boolean;
  complete: boolean;
  replanned: boolean;
  runStep: number;
  running: boolean;
  decision: ReplayDecision;
  heroSummary: HeroSummary | null;
  onControl: (decision: Exclude<ReplayDecision, null>) => void;
  onRun: () => void;
}) {
  return (
    <div className="mx-auto max-w-[1500px] px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-7 flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
        <div>
          <div className="mb-3 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-cyan-300">
            <span className="h-px w-6 bg-cyan-300/70" /> Proof-carrying physical
            AI
          </div>
          <h1 className="max-w-3xl text-3xl font-semibold leading-tight tracking-[-0.03em] text-white sm:text-4xl lg:text-[46px]">
            One sentence in.{' '}
            <span className="text-cyan-200">One verified mission out.</span>
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
            A judge-readable warehouse mission where AI proposes, deterministic
            rules decide, a human approves, and every transition carries
            evidence.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-slate-600">
              Current state
            </p>
            <p
              className={`mt-1 font-mono text-sm font-bold metric-${active.tone}`}
            >
              {decision === 'rejected' ? 'REJECTED' : active.state}
            </p>
          </div>
          <Button
            onClick={onRun}
            disabled={running}
            variant="outline"
            className="h-11 rounded-md border-cyan-200/25 bg-cyan-200/[0.06] px-5 text-xs font-bold text-cyan-100 hover:bg-cyan-200/[0.12]"
          >
            {complete ? (
              <RotateCcw className="size-4" />
            ) : (
              <Play className="size-4" />
            )}
            {running
              ? 'MISSION RUNNING'
              : complete
                ? 'REPLAY HERO'
                : 'RUN HERO'}
          </Button>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-2 border border-white/[0.08] bg-[#0a1828] sm:grid-cols-3 xl:grid-cols-6">
        {[
          [
            'Connection',
            'VERIFIED REPLAY',
            <RadioTower key="radio" className="size-3.5" />,
          ],
          [
            'State',
            active.state,
            <Activity key="state" className="size-3.5" />,
          ],
          [
            'Model latency',
            heroSummary?.model_calls
              ? `${heroSummary.model_calls
                  .slice(0, 2)
                  .reduce((sum, call) => sum + call.latency_ms, 0)
                  .toFixed(3)} ms`
              : 'loading',
            <Cpu key="cpu" className="size-3.5" />,
          ],
          [
            'Model cost',
            typeof heroSummary?.estimated_model_cost_usd === 'number'
              ? `$${heroSummary.estimated_model_cost_usd.toFixed(4)}`
              : 'loading',
            <Zap key="cost" className="size-3.5" />,
          ],
          ['Success', '20 / 20', <Check key="success" className="size-3.5" />],
          [
            'Safety',
            heroSummary?.safety_checks
              ? `${heroSummary.safety_checks.filter((check) => check.passed).length} / ${heroSummary.safety_checks.length} passed`
              : 'loading',
            <ShieldCheck key="shield" className="size-3.5" />,
          ],
        ].map(([label, value, icon]) => (
          <div
            key={label as string}
            className="border-b border-r border-white/[0.06] p-4 last:border-r-0 sm:border-b-0"
          >
            <div className="mb-1.5 flex items-center gap-2 text-[9px] uppercase tracking-[0.16em] text-slate-600">
              {icon}
              {label}
            </div>
            <div className="font-mono text-xs font-semibold text-slate-200">
              {value}
            </div>
          </div>
        ))}
      </div>

      <div className="mb-4 flex flex-col justify-between gap-3 border border-white/[0.08] bg-[#0a1828] p-3 sm:flex-row sm:items-center">
        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-slate-500">
            Local replay controls
          </p>
          <p className="mt-1 text-[10px] text-slate-600">
            Demonstrates UI states; authoritative operations are defined in
            openapi.json.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => onControl('approved')}
            className="border-emerald-300/20 bg-emerald-300/[0.05] text-emerald-200"
          >
            <Check className="size-3.5" /> Approve
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onControl('rejected')}
            className="border-rose-300/20 bg-rose-300/[0.05] text-rose-200"
          >
            <AlertTriangle className="size-3.5" /> Reject
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onControl('stopped')}
            className="border-amber-300/20 bg-amber-300/[0.05] text-amber-200"
          >
            <CircleStop className="size-3.5" /> Stop
          </Button>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.45fr_.8fr_.88fr]">
        <WarehouseMap
          blocked={blocked}
          complete={complete}
          replanned={replanned}
        />
        <SafetyCard
          blocked={blocked}
          complete={complete}
          replanned={replanned}
          runStep={runStep}
          heroSummary={heroSummary}
        />
        <TraceRail runStep={runStep} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.25fr_.75fr]">
        <MissionBrief
          active={active}
          complete={complete}
          heroSummary={heroSummary}
        />
        <TrustBoundary />
      </div>
    </div>
  );
}

function WarehouseMap({
  blocked,
  complete,
  replanned,
}: {
  blocked: boolean;
  complete: boolean;
  replanned: boolean;
}) {
  return (
    <Card className="overflow-hidden rounded-lg border-white/[0.09] bg-[#0a1828] shadow-none">
      <CardHeader className="flex-row items-center justify-between border-b border-white/[0.06] px-5 py-4">
        <div>
          <CardTitle className="text-xs font-semibold tracking-wide text-white">
            Live mission topology
          </CardTitle>
          <p className="mt-1 font-mono text-[9px] tracking-[0.1em] text-slate-600">
            WAREHOUSE WEST · SIMULATION FRAME 04
          </p>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-slate-500">
          <RadioTower className="size-3.5 text-emerald-300" />
          LOCAL TELEMETRY
        </div>
      </CardHeader>
      <CardContent className="map-grid relative min-h-[420px] p-0">
        <svg viewBox="0 0 760 460" className="absolute inset-0 h-full w-full">
          <title>
            Warehouse route from INBOUND-01 to RACK-A12 with a safe replan
            around a blocked aisle
          </title>
          <defs>
            <filter id="glow">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <pattern
              id="shelf"
              width="20"
              height="20"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M0 20V0H20"
                fill="none"
                stroke="#203a50"
                strokeWidth="1"
              />
            </pattern>
          </defs>
          {[55, 205, 355, 505].map((x) => (
            <rect
              key={x}
              x={x}
              y="55"
              width="100"
              height="62"
              rx="4"
              fill="url(#shelf)"
              stroke="#29445a"
            />
          ))}
          {[55, 205, 505].map((x) => (
            <rect
              key={`b${x}`}
              x={x}
              y="325"
              width="100"
              height="62"
              rx="4"
              fill="url(#shelf)"
              stroke="#29445a"
            />
          ))}
          <rect
            x="355"
            y="325"
            width="100"
            height="62"
            rx="4"
            fill="#112a34"
            stroke="#346057"
          />
          <text
            x="405"
            y="360"
            textAnchor="middle"
            fill="#66dca7"
            fontSize="11"
            fontFamily="monospace"
          >
            RACK-A12
          </text>
          <path
            d="M105 280 L225 280 L285 225 L405 225 L455 175 L555 175 L620 235"
            fill="none"
            stroke="#273d50"
            strokeWidth="14"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M105 280 L225 280 L285 225 L405 225 L455 175 L555 175 L620 235"
            fill="none"
            stroke="#4f7087"
            strokeWidth="2"
            strokeDasharray="8 9"
          />
          <path
            d="M105 280 L225 280 L285 225 L405 225"
            fill="none"
            stroke="#67e8e3"
            strokeWidth="7"
            strokeLinecap="round"
            filter="url(#glow)"
          />
          {replanned && (
            <path
              d="M405 225 C455 285 475 295 535 285 L610 285 C645 285 650 330 600 350 L455 355"
              fill="none"
              stroke="#a69cff"
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray="11 8"
              filter="url(#glow)"
            />
          )}
          {blocked && (
            <g transform="translate(440 176)">
              <circle r="20" fill="#341d24" stroke="#ff7285" />
              <path
                d="M-7-7L7 7M7-7L-7 7"
                stroke="#ff8a9a"
                strokeWidth="4"
                strokeLinecap="round"
              />
            </g>
          )}
          <g
            transform={`translate(${complete ? 455 : replanned ? 535 : blocked ? 405 : 285} ${complete ? 355 : replanned ? 285 : blocked ? 225 : 225})`}
            filter="url(#glow)"
          >
            <rect
              x="-20"
              y="-14"
              width="40"
              height="28"
              rx="7"
              fill="#67e8e3"
            />
            <circle cx="-11" cy="15" r="5" fill="#07111f" stroke="#67e8e3" />
            <circle cx="11" cy="15" r="5" fill="#07111f" stroke="#67e8e3" />
            <text
              y="4"
              textAnchor="middle"
              fill="#07111f"
              fontSize="10"
              fontWeight="800"
              fontFamily="monospace"
            >
              AGV-03
            </text>
          </g>
          <g transform="translate(105 280)">
            <circle r="8" fill="#07111f" stroke="#67e8e3" strokeWidth="3" />
            <text
              y="-17"
              textAnchor="middle"
              fill="#8da2b5"
              fontSize="10"
              fontFamily="monospace"
            >
              INBOUND-01
            </text>
          </g>
          <g transform="translate(455 355)">
            <circle r="9" fill="#66dca7" />
            <path
              d="M-4 0L-1 4L5-5"
              fill="none"
              stroke="#07111f"
              strokeWidth="2"
            />
          </g>
        </svg>
        <div className="absolute bottom-4 left-4 flex flex-wrap gap-2">
          <Badge
            variant="outline"
            className="border-cyan-300/20 bg-[#07111f]/80 font-mono text-[9px] text-cyan-200"
          >
            <span className="mr-1 h-0.5 w-4 bg-cyan-200" />
            EXECUTED
          </Badge>
          <Badge
            variant="outline"
            className="border-violet-300/20 bg-[#07111f]/80 font-mono text-[9px] text-violet-200"
          >
            <span className="mr-1 h-0.5 w-4 border-t-2 border-dashed border-violet-300" />
            REPLAN
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}

function SafetyCard({
  blocked,
  complete,
  replanned,
  runStep,
  heroSummary,
}: {
  blocked: boolean;
  complete: boolean;
  replanned: boolean;
  runStep: number;
  heroSummary: HeroSummary | null;
}) {
  const checks = [
    ['entity_validity', runStep >= 4],
    ['map_consistency', runStep >= 4],
    ['battery_reserve', runStep >= 4],
    ['vehicle_type', runStep >= 4],
    ['forbidden_zone', runStep >= 4],
    ['collision', runStep >= 4],
    ['reservation_availability', runStep >= 4],
    ['deadlock', runStep >= 4],
    ['destination_occupancy', runStep >= 4],
    ['proposal_semantics', runStep >= 4],
    ['approval_integrity', runStep >= 5],
  ];
  return (
    <Card className="rounded-lg border-white/[0.09] bg-[#0a1828] shadow-none">
      <CardHeader className="border-b border-white/[0.06] px-5 py-4">
        <CardTitle className="flex items-center justify-between text-xs text-white">
          <span className="flex items-center gap-2">
            <ShieldCheck className="size-4 text-emerald-300" />
            Safety proof
          </span>
          <Badge className="rounded-sm bg-emerald-300/10 font-mono text-[9px] text-emerald-300">
            DETERMINISTIC
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-5">
        <div className="space-y-2.5">
          {checks.map(([name, passed]) => (
            <div
              key={name as string}
              className="flex items-center justify-between border-b border-white/[0.045] pb-2.5 font-mono text-[10px]"
            >
              <span className="text-slate-400">{name}</span>
              {passed ? (
                <span className="flex items-center gap-1.5 text-emerald-300">
                  <Check className="size-3" />
                  PASS
                </span>
              ) : (
                <span className="text-slate-700">PENDING</span>
              )}
            </div>
          ))}
        </div>
        {blocked && (
          <div className="mt-4 border border-rose-300/20 bg-rose-300/[0.055] p-3">
            <div className="flex items-center gap-2 text-[10px] font-bold text-rose-200">
              <AlertTriangle className="size-3.5" />
              LOCAL STOP ASSERTED
            </div>
            <p className="mt-1.5 font-mono text-[9px] leading-4 text-slate-500">
              simulator process ·{' '}
              {heroSummary
                ? `${heroSummary.stop_latency_ms.toFixed(6)} ms`
                : 'loading measured trace'}
            </p>
          </div>
        )}
        {replanned && (
          <div className="mt-3 flex items-center gap-2 border border-violet-300/20 bg-violet-300/[0.055] p-3 font-mono text-[9px] text-violet-200">
            <Route className="size-3.5" />
            REPLAN PROOF SEALED
          </div>
        )}
        {complete && (
          <div className="mt-3 flex items-center gap-2 border border-emerald-300/20 bg-emerald-300/[0.055] p-3 font-mono text-[9px] text-emerald-200">
            <FileCheck2 className="size-3.5" />
            OUTCOME VERIFIED
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TraceRail({ runStep }: { runStep: number }) {
  return (
    <Card className="rounded-lg border-white/[0.09] bg-[#0a1828] shadow-none">
      <CardHeader className="border-b border-white/[0.06] px-5 py-4">
        <CardTitle className="flex items-center justify-between text-xs text-white">
          <span className="flex items-center gap-2">
            <TerminalSquare className="size-4 text-cyan-200" />
            Evidence trace
          </span>
          <span className="font-mono text-[9px] font-normal text-slate-600">
            SHA-256 CHAIN
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="max-h-[486px] overflow-y-auto p-5">
        <ol className="relative ml-1 border-l border-white/[0.09]">
          {timeline.map((item, index) => {
            const visible = index <= runStep;
            const current = index === runStep;
            return (
              <li
                key={`${item.event}-${index}`}
                className={classNames(
                  'relative ml-5 pb-5 transition-all duration-300 last:pb-0',
                  !visible && 'opacity-20',
                )}
              >
                <span
                  className={classNames(
                    'absolute -left-[25px] top-1 size-2 rounded-full border',
                    visible
                      ? `status-${item.tone}`
                      : 'border-slate-700 bg-[#0a1828]',
                    current && 'ring-4 ring-cyan-200/10',
                  )}
                />
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={`font-mono text-[9px] font-bold tracking-[0.06em] metric-${item.tone}`}
                  >
                    {item.state}
                  </span>
                  <span className="font-mono text-[8px] text-slate-700">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                </div>
                <p className="mt-1 font-mono text-[9px] text-slate-400">
                  {item.event}
                </p>
                {current && (
                  <p className="mt-1.5 text-[10px] leading-4 text-slate-500">
                    {item.detail}
                  </p>
                )}
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}

function MissionBrief({
  active,
  complete,
  heroSummary,
}: {
  active: (typeof timeline)[number];
  complete: boolean;
  heroSummary: HeroSummary | null;
}) {
  return (
    <Card className="rounded-lg border-white/[0.09] bg-[#0a1828] shadow-none">
      <CardContent className="grid gap-6 p-5 sm:grid-cols-[1fr_auto] sm:items-center">
        <div>
          <div className="mb-2 flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.15em] text-slate-600">
            <MapPinned className="size-3.5" />
            Natural-language intent
          </div>
          <p className="text-base font-medium text-white">
            “Move pallet P-104 from INBOUND-01 to RACK-A12.”
          </p>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            Current event:{' '}
            <span className={`font-mono metric-${active.tone}`}>
              {active.event}
            </span>{' '}
            · {active.detail}
          </p>
        </div>
        <div className="flex gap-3 sm:text-right">
          <div className="border-l border-white/[0.08] pl-4">
            <p className="font-mono text-[9px] text-slate-600">PROPOSAL</p>
            <p className="mt-1 max-w-32 truncate font-mono text-xs text-slate-300">
              {heroSummary?.proposal_id ?? 'loading'}
            </p>
          </div>
          <div className="border-l border-white/[0.08] pl-4">
            <p className="font-mono text-[9px] text-slate-600">OUTCOME</p>
            <p
              className={classNames(
                'mt-1 font-mono text-xs',
                complete ? 'text-emerald-300' : 'text-slate-600',
              )}
            >
              {complete ? 'VERIFIED' : 'PENDING'}
            </p>
            {complete && heroSummary?.final_pose && (
              <p className="mt-1 whitespace-nowrap font-mono text-[9px] text-emerald-200/75">
                {heroSummary.final_pose.node_id} · x {heroSummary.final_pose.x.toFixed(1)} · y{' '}
                {heroSummary.final_pose.y.toFixed(1)} · θ{' '}
                {heroSummary.final_pose.heading_deg.toFixed(1)}°
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function TrustBoundary() {
  return (
    <Card className="rounded-lg border-white/[0.09] bg-[#0a1828] shadow-none">
      <CardContent className="flex h-full items-center gap-4 p-5">
        <div className="grid size-10 shrink-0 place-items-center rounded-md border border-violet-300/20 bg-violet-300/[0.07]">
          <Cpu className="size-5 text-violet-200" />
        </div>
        <div>
          <p className="text-xs font-semibold text-white">
            AI proposes. Rules authorize.
          </p>
          <p className="mt-1 text-[11px] leading-5 text-slate-500">
            No model output crosses the actuation boundary without schema,
            safety proof and human approval.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function ArchitectureView({ onRun }: { onRun: () => void }) {
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-10 grid gap-7 lg:grid-cols-[1fr_.7fr] lg:items-end">
        <div>
          <div className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-violet-300">
            Architecture / trust boundaries
          </div>
          <h1 className="text-3xl font-semibold tracking-[-0.03em] text-white sm:text-4xl">
            Intelligence above.
            <br />
            <span className="text-violet-200">Authority below.</span>
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-400">
            The design separates probabilistic reasoning from deterministic
            authorization, then preserves the relationship in a tamper-evident
            evidence chain.
          </p>
        </div>
        <div className="flex justify-start lg:justify-end">
          <Button
            onClick={onRun}
            className="rounded-md bg-violet-200 text-[#07111f] hover:bg-violet-100"
          >
            <Play className="size-4" />
            Watch the boundary in action
          </Button>
        </div>
      </div>
      <div className="space-y-3">
        {architectureLayers.map((layer, index) => {
          const Icon = layer.icon;
          return (
            <div
              key={layer.number}
              className="group grid gap-4 border border-white/[0.08] bg-[#0a1828] p-5 transition-colors hover:border-violet-300/20 sm:grid-cols-[60px_48px_1fr_auto] sm:items-center"
            >
              <span className="font-mono text-xs text-slate-700">
                {layer.number}
              </span>
              <div className="grid size-10 place-items-center rounded border border-white/[0.08] bg-white/[0.025]">
                <Icon
                  className={classNames(
                    'size-5',
                    index === 1 || index === 4
                      ? 'text-emerald-300'
                      : 'text-violet-200',
                  )}
                />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">
                  {layer.title}
                </h2>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  {layer.detail}
                </p>
              </div>
              <Badge
                variant="outline"
                className="w-fit rounded-sm border-white/[0.1] font-mono text-[9px] text-slate-400"
              >
                {layer.label}
              </Badge>
            </div>
          );
        })}
      </div>
      <div className="mt-5 grid gap-4 md:grid-cols-3">
        <BoundaryCard
          icon={KeyRound}
          title="Approval is content-bound"
          detail="Operator identity, proposal digest, policy digest and expiry are signed together."
        />
        <BoundaryCard
          icon={Zap}
          title="Stop is local"
          detail="Emergency response does not depend on model latency, cloud reachability or tool availability."
        />
        <BoundaryCard
          icon={FileCheck2}
          title="Claims are scoped"
          detail="Simulator replay and live Token Factory receipts are labeled separately; neither is presented as physical AGV evidence."
        />
      </div>
    </div>
  );
}

function BoundaryCard({
  icon: Icon,
  title,
  detail,
}: {
  icon: typeof KeyRound;
  title: string;
  detail: string;
}) {
  return (
    <Card className="rounded-lg border-white/[0.08] bg-[#0a1828] shadow-none">
      <CardContent className="p-5">
        <Icon className="mb-4 size-5 text-cyan-200" />
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <p className="mt-2 text-xs leading-5 text-slate-500">{detail}</p>
      </CardContent>
    </Card>
  );
}

function EvidenceView({
  heroSummary,
  scenarioMetrics,
  judgeLoad,
  impactLoad,
  screenshotEvidence,
  liveGate,
  evidenceError,
}: {
  heroSummary: HeroSummary | null;
  scenarioMetrics: ScenarioMetrics | null;
  judgeLoad: JudgeLoadEvidence | null;
  impactLoad: ImpactLoadModel | null;
  screenshotEvidence: ScreenshotEvidence | null;
  liveGate: LiveGateEvidence | null;
  evidenceError: boolean;
}) {
  return (
    <div className="mx-auto max-w-[1300px] px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-9 flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
        <div>
          <div className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-emerald-300">
            Evidence / reference simulator
          </div>
          <h1 className="text-3xl font-semibold tracking-[-0.03em] text-white sm:text-4xl">
            100 scenarios.{' '}
            <span className="text-emerald-200">Zero silent failures.</span>
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-400">
            A deterministic, reproducible offline suite spanning nominal
            delivery and five safety-critical edge-case families.
          </p>
        </div>
        <a href="/data/evidence-bundle.zip" download>
          <Button
            variant="outline"
            className="rounded-md border-emerald-300/25 bg-emerald-300/[0.06] text-emerald-100 hover:bg-emerald-300/[0.12]"
          >
            <Download className="size-4" />
            Download evidence bundle
          </Button>
        </a>
      </div>

      <div className="mb-4 grid grid-cols-2 border border-white/[0.08] bg-[#0a1828] md:grid-cols-3 xl:grid-cols-6">
        <Metric
          value={
            scenarioMetrics
              ? `${scenarioMetrics.validated_count}/${scenarioMetrics.sample_size}`
              : '—'
          }
          label="Valid scenario outcomes"
          tone="cyan"
        />
        <Metric
          value={
            scenarioMetrics ? `${scenarioMetrics.safety_violation_count}` : '—'
          }
          label="Safety violations"
          tone="emerald"
        />
        <Metric
          value={
            scenarioMetrics
              ? `${Math.round(scenarioMetrics.unsafe_plan_rejection_recall * 100)}%`
              : '—'
          }
          label="Unsafe-condition recall"
          tone="violet"
        />
        <Metric value="20/20" label="Consecutive Hero runs" tone="emerald" />
        <Metric
          value={judgeLoad ? `${judgeLoad.p95_ms.toFixed(0)} ms` : '—'}
          label="Judge load p95"
          tone={judgeLoad?.acceptance_passed ? 'emerald' : 'amber'}
        />
        <Metric value="400–500" label="Pallets/day modeled" tone="violet" />
      </div>

      <Card className="mb-4 rounded-lg border-emerald-300/20 bg-emerald-300/[0.035] shadow-none">
        <CardHeader className="border-b border-emerald-300/10 px-5 py-4">
          <CardTitle className="flex flex-wrap items-center justify-between gap-3 text-xs text-white">
            <span className="flex items-center gap-2">
              <RadioTower className="size-4 text-emerald-300" />
              Live Nebius Token Factory Compatibility Gate
            </span>
            <Badge className="rounded-sm bg-emerald-300/10 font-mono text-[8px] text-emerald-300">
              {liveGate?.official_gate_passed ? 'OFFICIAL GATE · PASS' : 'VERIFYING'}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-5">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <EvidenceStat
              label="Live runs"
              value={
                liveGate
                  ? `${liveGate.metrics.completed_runs}/${liveGate.metrics.requested_runs}`
                  : '—'
              }
            />
            <EvidenceStat
              label="Forced tool calls"
              value={liveGate ? `${liveGate.metrics.completed_runs * 3}` : '—'}
            />
            <EvidenceStat
              label="First / repaired schema"
              value={
                liveGate
                  ? `${(liveGate.metrics.first_schema_valid_rate * 100).toFixed(0)}% / ${(liveGate.metrics.post_repair_schema_valid_rate * 100).toFixed(0)}%`
                  : '—'
              }
            />
            <EvidenceStat
              label="Intent→proposal p95"
              value={
                liveGate
                  ? `${liveGate.metrics.intent_to_proposal_p95_seconds.toFixed(3)} s`
                  : '—'
              }
            />
            <EvidenceStat
              label="Failures"
              value={liveGate ? `${liveGate.failures.length}` : '—'}
            />
          </div>
          <p className="mt-4 break-all font-mono text-[9px] leading-4 text-slate-500">
            {liveGate
              ? `${liveGate.provider} · ${liveGate.model} · report ${liveGate.report_hash}`
              : 'Loading signed-off aggregate report…'}
          </p>
          <p className="mt-2 text-[10px] leading-5 text-slate-500">
            Live model/provider evidence over the reference simulator. This does not claim physical AGV execution.
          </p>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
        <Card className="rounded-lg border-white/[0.09] bg-[#0a1828] shadow-none">
          <CardHeader className="border-b border-white/[0.06] px-5 py-4">
            <CardTitle className="text-xs text-white">
              Scenario families
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5 p-5">
            {suites.map(([id, label, count, color]) => (
              <div key={id}>
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-[9px] text-slate-600">
                      {id}
                    </span>
                    <span className="text-xs text-slate-300">{label}</span>
                  </div>
                  <span className="font-mono text-[10px] text-slate-500">
                    {count}/{count}
                  </span>
                </div>
                <div className="h-1.5 bg-white/[0.05]">
                  <div
                    className="h-full"
                    style={{ width: '100%', background: color }}
                  />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card className="rounded-lg border-white/[0.09] bg-[#0a1828] shadow-none">
          <CardHeader className="border-b border-white/[0.06] px-5 py-4">
            <CardTitle className="flex items-center gap-2 text-xs text-white">
              <Fingerprint className="size-4 text-emerald-300" />
              Reproducibility manifest
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <dl className="space-y-4">
              {[
                ['Seed', '2002'],
                ['Policy', 'safety-policy.json'],
                ['State machine', 'workflow-state-machine.json'],
                ['Source status', 'BOUND TO RUN MANIFEST'],
                ['Execution', 'REFERENCE_SIMULATOR'],
                [
                  'Hero trace',
                  evidenceError
                    ? 'LOAD ERROR'
                    : heroSummary?.trace_chain_valid
                      ? `${heroSummary.trace_id} · VALID`
                      : 'VERIFYING',
                ],
              ].map(([term, value]) => (
                <div key={term} className="border-b border-white/[0.05] pb-3">
                  <dt className="font-mono text-[9px] uppercase tracking-[0.12em] text-slate-600">
                    {term}
                  </dt>
                  <dd className="mt-1.5 break-all font-mono text-[10px] text-slate-300">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
            <div className="mt-5 flex flex-col gap-2">
              <EvidenceLink href="/data/metrics.json" label="metrics.json" />
              <EvidenceLink
                href="/data/run-manifest.json"
                label="run-manifest.json"
              />
              <EvidenceLink
                href="/data/preflight-report.json"
                label="compatibility-preflight.json"
              />
              <EvidenceLink
                href="/data/live-gate.json"
                label="compatibility-live-gate.json"
              />
              <EvidenceLink
                href="/data/hero-reliability.json"
                label="hero-reliability.json"
              />
              <EvidenceLink
                href="/data/hero-summary.json"
                label="hero-summary.json"
              />
              <EvidenceLink
                href="/data/screenshot-manifest.json"
                label="screenshot-manifest.json"
              />
              <EvidenceLink
                href="/data/baseline-comparison.json"
                label="manual-vs-agent-baseline.json"
              />
              <EvidenceLink href="/data/openapi.json" label="openapi.json" />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.15fr_.85fr]">
        <Card className="rounded-lg border-white/[0.09] bg-[#0a1828] shadow-none">
          <CardHeader className="border-b border-white/[0.06] px-5 py-4">
            <CardTitle className="flex items-center justify-between gap-2 text-xs text-white">
              <span className="flex items-center gap-2">
                <TerminalSquare className="size-4 text-violet-200" />
                Fixture replay tool evidence
              </span>
              <Badge className="rounded-sm border border-rose-300/20 bg-rose-300/[0.08] font-mono text-[8px] text-rose-200">
                MOCK / FIXTURE
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 p-5 sm:grid-cols-2">
            {heroSummary?.model_calls?.map((call) => (
              <div
                key={`${call.request_id}-${call.tool_name}`}
                className="border border-white/[0.07] bg-white/[0.02] p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[10px] text-violet-200">
                    {call.tool_name}
                  </span>
                  <span className="font-mono text-[9px] text-slate-500">
                    {call.latency_ms.toFixed(3)} ms
                  </span>
                </div>
                <p className="mt-2 truncate font-mono text-[9px] text-slate-600">
                  {call.provider} / {call.model}
                </p>
                <p className="mt-1 truncate font-mono text-[9px] text-slate-600">
                  args {call.tool_arguments_hash.slice(0, 12)}… · result{' '}
                  {call.tool_result_hash.slice(0, 12)}…
                </p>
              </div>
            )) ?? (
              <p className="text-xs text-slate-500">
                Loading verified tool spans…
              </p>
            )}
            {heroSummary?.operation_metrics && (
              <div className="border border-cyan-300/15 bg-cyan-300/[0.035] p-3 sm:col-span-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-[10px] text-cyan-200">
                    get_operation_metrics
                  </span>
                  <span className="font-mono text-[9px] text-emerald-300">
                    {heroSummary.operation_metrics.completed ? 'TYPED RESULT · PASS' : 'INCOMPLETE'}
                  </span>
                </div>
                <p className="mt-2 font-mono text-[9px] leading-4 text-slate-500">
                  {heroSummary.operation_metrics.schema_version} · mission{' '}
                  {heroSummary.operation_metrics.mission_id} · sample n={heroSummary.operation_metrics.sample_size} ·{' '}
                  {heroSummary.operation_metrics.total_duration_ms.toFixed(3)} ms ·{' '}
                  {heroSummary.operation_metrics.human_interventions} human approval
                </p>
              </div>
            )}
          </CardContent>
        </Card>
        <Card className="rounded-lg border-white/[0.09] bg-[#0a1828] shadow-none">
          <CardHeader className="border-b border-white/[0.06] px-5 py-4">
            <CardTitle className="text-xs text-white">
              Release acceptance boundary
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 p-5">
            {[
              ['A05', '100-scenario simulator suite', 'PASS', 'emerald'],
              ['A03', '20 consecutive Hero replays', 'SIMULATOR', 'cyan'],
              [
                'A01–A02',
                'Live Nebius runtime + compatibility',
                liveGate?.official_gate_passed ? 'LIVE PASS' : 'VERIFYING',
                liveGate?.official_gate_passed ? 'emerald' : 'amber',
              ],
              ['A06–A07', 'Physical stop and AGV loop', 'HARDWARE', 'amber'],
              [
                'A09–A12',
                'Public links, video, submission',
                'RELEASE',
                'violet',
              ],
            ].map(([id, label, status, tone]) => (
              <div
                key={id}
                className="grid grid-cols-[60px_1fr_auto] items-center gap-3 border-b border-white/[0.05] py-2"
              >
                <span className="font-mono text-[9px] text-slate-600">
                  {id}
                </span>
                <span className="text-[11px] text-slate-400">{label}</span>
                <span className={`font-mono text-[9px] metric-${tone}`}>
                  {status}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card className="rounded-lg border-white/[0.09] bg-[#0a1828] shadow-none">
          <CardHeader className="border-b border-white/[0.06] px-5 py-4">
            <CardTitle className="flex items-center justify-between gap-3 text-xs text-white">
              <span className="flex items-center gap-2">
                <Zap className="size-4 text-cyan-200" /> Judge Mode first-load evidence
              </span>
              <Badge className="rounded-sm bg-emerald-300/10 font-mono text-[8px] text-emerald-300">
                {judgeLoad?.acceptance_passed ? 'PASS' : 'VERIFYING'}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <div className="grid grid-cols-3 gap-3">
              <EvidenceStat label="Samples" value={judgeLoad ? `${judgeLoad.sample_count}` : '—'} />
              <EvidenceStat label="Median" value={judgeLoad ? `${judgeLoad.median_ms.toFixed(0)} ms` : '—'} />
              <EvidenceStat label="p95 / limit" value={judgeLoad ? `${judgeLoad.p95_ms.toFixed(0)} / ${judgeLoad.threshold_ms} ms` : '—'} />
            </div>
            <p className="mt-4 text-[10px] leading-5 text-slate-500">
              Local production build · browser end-to-end load timing · one new-tab navigation plus 19 same-tab reloads.
            </p>
            <EvidenceLink href="/data/judge-mode-load.json" label="judge-mode-load.json" />
          </CardContent>
        </Card>

        <Card className="rounded-lg border-white/[0.09] bg-[#0a1828] shadow-none">
          <CardHeader className="border-b border-white/[0.06] px-5 py-4">
            <CardTitle className="flex items-center justify-between gap-3 text-xs text-white">
              <span className="flex items-center gap-2">
                <Activity className="size-4 text-violet-200" /> 400–500 pallets/day stress model
              </span>
              <Badge className="rounded-sm bg-violet-300/10 font-mono text-[8px] text-violet-200">
                PROJECTION · NOT PHYSICAL
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <div className="space-y-2">
              {impactLoad?.loads.map((row) => (
                <div key={row.pallets_per_day} className="grid grid-cols-[80px_1fr_auto] items-center gap-3 border-b border-white/[0.05] py-2 font-mono text-[9px]">
                  <span className="text-slate-300">{row.pallets_per_day}/day</span>
                  <span className="text-slate-500">
                    util {(row.agv_metrics.mean_utilization * 100).toFixed(1)}% · p95 wait {row.agv_metrics.p95_queue_wait_seconds.toFixed(0)}s
                  </span>
                  <span className="text-violet-200">save {row.operator_impact.hours_saved_per_day.toFixed(1)}h*</span>
                </div>
              )) ?? <p className="text-xs text-slate-500">Loading projection…</p>}
            </div>
            <p className="mt-4 text-[10px] leading-5 text-slate-500">
              *Seeded M/G/2 planning projection, 20 simulated days per load. Assumptions are explicit and are not observed site labor or physical throughput.
            </p>
            <EvidenceLink href="/data/impact-load-model.json" label="impact-load-model.json" />
          </CardContent>
        </Card>
      </div>

      <div className="mt-4 border border-amber-300/20 bg-amber-300/[0.045] p-4">
        <div className="flex gap-3">
          <LockKeyhole className="mt-0.5 size-4 shrink-0 text-amber-200" />
          <div>
            <p className="text-xs font-semibold text-amber-100">
              Final evidence gate intentionally remains closed
            </p>
            <p className="mt-1 text-[11px] leading-5 text-slate-500">
              {screenshotEvidence?.final_submission_eligible
                ? 'The three screenshots are bound to a passing live-provider gate and are eligible for final review.'
                : liveGate?.official_gate_passed
                  ? 'The live Compatibility Gate passes. The three current PNGs remain preflight-only MOCK / FIXTURE captures and must be replaced only after the correlated physical AGV run and safety review.'
                  : 'The three current PNGs are preflight-only MOCK / FIXTURE captures and cannot satisfy final submission.'}
            </p>
            <Badge
              variant="outline"
              className="mt-3 border-amber-300/20 bg-amber-300/[0.06] font-mono text-[9px] text-amber-200"
            >
              {screenshotEvidence?.final_submission_eligible
                ? 'FINAL LIVE EVIDENCE'
                : 'RECAPTURE REQUIRED'}
            </Badge>
          </div>
        </div>
      </div>
    </div>
  );
}

function SourceView() {
  const requiredFiles = [
    'README.md + LICENSE',
    'PRE_EXISTING_WORK.md',
    'SECURITY.md + THIRD_PARTY_NOTICES.md',
    'docker-compose.yml + Dockerfile',
    'apps / services / adapters / schemas / scenarios / tests',
    'Evidence Bundle with reproducibility hashes',
  ];
  return (
    <div className="mx-auto max-w-[1100px] px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-8">
        <div className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-cyan-300">
          GitHub / source release gate
        </div>
        <h1 className="text-3xl font-semibold tracking-[-0.03em] text-white sm:text-4xl">
          Source is release-ready.{' '}
          <span className="text-amber-200">Publication is not authorized.</span>
        </h1>
        <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
          The local repository contains the required public boundary, build
          instructions, licenses, disclosures, schemas, simulator and evidence.
          No GitHub remote is configured, so this page does not invent a public
          URL.
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_.7fr]">
        <Card className="rounded-lg border-white/[0.09] bg-[#0a1828] shadow-none">
          <CardHeader className="border-b border-white/[0.06] px-5 py-4">
            <CardTitle className="flex items-center gap-2 text-xs text-white">
              <GitBranch className="size-4 text-cyan-200" /> Repository
              checklist
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 p-5">
            {requiredFiles.map((file) => (
              <div
                key={file}
                className="flex items-center gap-3 text-xs text-slate-300"
              >
                <Check className="size-4 shrink-0 text-emerald-300" /> {file}
              </div>
            ))}
          </CardContent>
        </Card>
        <Card className="rounded-lg border-amber-300/20 bg-amber-300/[0.035] shadow-none">
          <CardContent className="p-6">
            <LockKeyhole className="mb-4 size-6 text-amber-200" />
            <p className="text-sm font-semibold text-white">
              Public remote pending
            </p>
            <p className="mt-2 text-xs leading-5 text-slate-400">
              A public GitHub, GitLab or Bitbucket URL must be supplied before
              A10 and the anonymous Judge path can pass. Publishing is a
              deliberate IP exposure action and remains outside this private
              replay.
            </p>
            <Badge
              variant="outline"
              className="mt-5 border-amber-300/20 bg-amber-300/[0.06] font-mono text-[9px] text-amber-200"
            >
              NO PUBLIC REMOTE CONFIGURED
            </Badge>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Metric({
  value,
  label,
  tone,
}: {
  value: string;
  label: string;
  tone: string;
}) {
  return (
    <div className="border-b border-r border-white/[0.06] p-5 last:border-r-0 lg:border-b-0">
      <p
        className={`font-mono text-2xl font-semibold tracking-[-0.04em] metric-${tone}`}
      >
        {value}
      </p>
      <p className="mt-2 text-[10px] uppercase tracking-[0.12em] text-slate-600">
        {label}
      </p>
    </div>
  );
}

function EvidenceStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-white/[0.06] bg-white/[0.02] p-3">
      <p className="font-mono text-sm font-semibold text-cyan-100">{value}</p>
      <p className="mt-1 text-[8px] uppercase tracking-[0.12em] text-slate-600">
        {label}
      </p>
    </div>
  );
}

function EvidenceLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      download
      className="flex items-center justify-between border border-white/[0.07] bg-white/[0.02] px-3 py-2 font-mono text-[10px] text-slate-400 transition-colors hover:border-cyan-300/20 hover:text-cyan-200"
    >
      <span>{label}</span>
      <ChevronRight className="size-3" />
    </a>
  );
}
