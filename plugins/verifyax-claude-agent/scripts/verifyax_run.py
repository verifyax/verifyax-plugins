"""Drive a full VerifyAX evaluation of an A2A agent: connectivity test ->
register -> generate scenario -> run simulation -> fetch scores.

Used by the `connect-to-verifyax` skill, and runnable standalone:

    export VERIFYAX_API_KEY=sk-ver-api-...
    python scripts/verifyax_run.py \
        --agent-url https://<your-tunnel> \
        --agent-key <A2A_API_KEY the agent expects> \
        --name "Claude Agent (tools-off)" \
        --tags task_decomposition tradeoff_reasoning \
        --context "A user brings a complex planning problem..." \
        --timeout-ms 180000

    # Just list selectable tags for a scenario type:
    python scripts/verifyax_run.py --list-tags --scenario-type info_exchange

Depends on httpx (a transitive dep of a2a-sdk; `pip install httpx` otherwise).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import httpx

DEFAULT_BASE = os.environ.get("VERIFYAX_BASE_URL", "https://console.verifyax.com/api/v1")
# The skill-tag catalogue lives on the gateway *web* route (no API key).
TAGS_URL = "https://console.verifyax.com/web/api/v1/tags"


def _key() -> str:
    k = os.environ.get("VERIFYAX_API_KEY")
    if not k:
        sys.exit("VERIFYAX_API_KEY is not set.")
    return k


def _client(base: str) -> httpx.Client:
    return httpx.Client(
        base_url=base,
        headers={"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"},
        timeout=60.0,
    )


def list_tags(scenario_type: str) -> list[dict]:
    r = httpx.get(TAGS_URL, timeout=30.0)
    r.raise_for_status()
    data = r.json().get("data", [])
    out = []
    for t in data:
        allowed = t.get("allowed_scenario_types")
        if allowed is None or scenario_type in allowed:
            out.append(t)
    return out


def test_agent_card(c: httpx.Client, agent_url: str, agent_key: str) -> dict:
    r = c.post(
        "/agents/tests/agent-card",
        json={
            "agent_url": agent_url,
            "agent_type": "A2A",
            "agent_parameters": {"auth_method": "bearer", "token": agent_key},
        },
    )
    r.raise_for_status()
    return r.json()


def register_agent(c: httpx.Client, *, name: str, agent_url: str, agent_key: str,
                   description: str, timeout_ms: int) -> str:
    r = c.post(
        "/agents",
        json={
            "name": name,
            "description": description,
            "agent_url": agent_url,
            "agent_type": "A2A",
            "agent_parameters": {
                "auth_method": "bearer",
                "token": agent_key,
                "timeout": timeout_ms,
                "max_requests_per_minute": 4,
            },
        },
    )
    r.raise_for_status()
    return r.json()["uuid"]


def generate_scenario(c: httpx.Client, *, name: str, scenario_type: str,
                      context_prompt: str, tags: list[str]) -> tuple[str, str]:
    r = c.post(
        "/scenarios/generate",
        json={
            "name": name,
            "scenario_type": scenario_type,
            "context_prompt": context_prompt,
            "tags": tags,
            "num_scenarios": 1,
            "timeout_minutes": 30,
        },
    )
    r.raise_for_status()
    d = r.json()
    return d["uuid"], d["job_uuid"]


def poll_job(c: httpx.Client, job_uuid: str, *, every: int = 15, tries: int = 40) -> str:
    for _ in range(tries):
        r = c.get(f"/jobs/{job_uuid}")
        r.raise_for_status()
        d = r.json()
        st = (d.get("current_status") or "").upper()
        print(f"  job {job_uuid[:8]}: {st}")
        if st == "COMPLETED":
            return st
        if st in ("FAILED", "CANCELLED"):
            sys.exit(f"scenario job {st}: {d.get('error_details')}")
        time.sleep(every)
    sys.exit("scenario job did not complete in time")


def credit_preview(c: httpx.Client, scenario_uuid: str, agent_uuid: str, num_runs: int) -> dict:
    r = c.post(
        "/engine/workspace-credit-preview",
        json={"mode": "scenario_run", "scenario_uuid": scenario_uuid,
              "num_runs": num_runs, "agent_uuid": agent_uuid},
    )
    r.raise_for_status()
    return r.json()


def simulate(c: httpx.Client, scenario_uuid: str, agent_uuid: str, num_runs: int) -> dict:
    r = c.post(
        "/engine/simulate/scenario",
        json={"scenario_uuid": scenario_uuid, "agent_uuid": agent_uuid,
              "evaluate_on_complete": True, "num_runs": num_runs},
    )
    r.raise_for_status()
    return r.json()


def poll_sim(c: httpx.Client, sim_uuid: str, *, every: int = 15, tries: int = 80) -> str:
    for _ in range(tries):
        r = c.get(f"/simulations/{sim_uuid}")
        r.raise_for_status()
        st = (r.json().get("status") or "").upper()
        print(f"  sim {sim_uuid[:8]}: {st}")
        if st == "COMPLETED":
            return st
        if st in ("FAILED", "CANCELLED"):
            sys.exit(f"simulation {st}")
        time.sleep(every)
    sys.exit("simulation did not complete in time")


def fetch_eval(c: httpx.Client, eval_job_uuid: str, *, every: int = 15, tries: int = 20) -> dict:
    for _ in range(tries):
        r = c.get(f"/simulations/evaluations/{eval_job_uuid}")
        r.raise_for_status()
        d = r.json()
        st = (d.get("current_status") or d.get("status") or "").upper()
        if st == "COMPLETED":
            return d
        if st in ("FAILED", "CANCELLED"):
            sys.exit(f"evaluation {st}")
        print(f"  eval {eval_job_uuid[:8]}: {st}")
        time.sleep(every)
    sys.exit("evaluation did not complete in time")


def print_results(d: dict) -> None:
    ev = d.get("evaluation") or {}
    print("\n=== EVALUATION ===")
    succ = ev.get("success")
    if isinstance(succ, dict):
        print("SUCCESS:", succ.get("success"), "-", succ.get("reasoning", "")[:200])
    for e in ev.get("evaluations", []):
        print(f"  {e.get('tag')}: grade={e.get('grade')}")
        if e.get("reason"):
            print("     ", e["reason"][:300])
    if ev.get("executive_summary"):
        print("\nSUMMARY:", ev["executive_summary"][:800])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-url")
    ap.add_argument("--agent-key", default=os.environ.get("A2A_API_KEY"))
    ap.add_argument("--name", default="Claude Agent under evaluation")
    ap.add_argument("--description", default="A Claude Code agent exposed over A2A.")
    ap.add_argument("--tags", nargs="+", default=[])
    ap.add_argument("--context", default="")
    ap.add_argument("--scenario-type", default="info_exchange")
    ap.add_argument("--num-runs", type=int, default=1)
    ap.add_argument("--timeout-ms", type=int, default=180000)
    ap.add_argument("--list-tags", action="store_true")
    ap.add_argument("--base", default=DEFAULT_BASE)
    args = ap.parse_args()

    if args.list_tags:
        for t in list_tags(args.scenario_type):
            print(f"{t['name']:<34} {t.get('category',''):<20} bench={t.get('benchmark_family')}")
        return 0

    if not (args.agent_url and args.agent_key and args.tags):
        sys.exit("Need --agent-url, --agent-key, and --tags (or --list-tags).")

    with _client(args.base) as c:
        print("Testing agent card...")
        card = test_agent_card(c, args.agent_url, args.agent_key)
        print("  card OK:", (card.get("data") or card).get("name"))

        print("Registering agent...")
        agent_uuid = register_agent(
            c, name=args.name, agent_url=args.agent_url, agent_key=args.agent_key,
            description=args.description, timeout_ms=args.timeout_ms,
        )
        print("  agent_uuid:", agent_uuid)

        print("Generating scenario...")
        scenario_uuid, job_uuid = generate_scenario(
            c, name=f"{args.name} — {'+'.join(args.tags)}",
            scenario_type=args.scenario_type, context_prompt=args.context, tags=args.tags,
        )
        poll_job(c, job_uuid)
        print("  scenario_uuid:", scenario_uuid)

        prev = credit_preview(c, scenario_uuid, agent_uuid, args.num_runs)
        print(f"  est credits: {prev.get('newRunEstimatedCredits')} (balance {prev.get('balance')})")

        print("Triggering simulation...")
        sim = simulate(c, scenario_uuid, agent_uuid, args.num_runs)
        sim_uuid = sim["simulation_uuid"]
        eval_job = sim.get("evaluation_job_uuid")
        print("  simulation_uuid:", sim_uuid)
        poll_sim(c, sim_uuid)

        print("Fetching evaluation...")
        result = fetch_eval(c, eval_job)
        print_results(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
