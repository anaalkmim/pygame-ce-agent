"""Run the evaluation set against the live agent.

Each case runs several times, because the same question has been
observed to produce different claims on different runs. A case only
counts as reliable if every run passes.

This makes real API calls and costs money.

Usage: python scripts/run_eval.py [runs_per_case]
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.agent import ask, build_client  # noqa: E402
from src.scoring import load_cases, score, stability  # noqa: E402

CASES_PATH = ROOT / "data" / "eval_cases.json"
RESULTS_PATH = ROOT / "outputs" / "eval_results.json"
DEFAULT_RUNS = 3


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RUNS
    cases = load_cases(CASES_PATH)

    print(f"{len(cases)} cases, {runs} runs each = {len(cases) * runs} calls\n")

    client, mcp_servers = build_client()
    records = []
    reliable = 0

    for case in cases:
        print(f"{case.id}")
        verdicts = []

        for attempt in range(runs):
            try:
                answer, tool_calls = ask(client, mcp_servers, case.question)
            except Exception as error:
                print(f"  run {attempt + 1}: request failed: {error}")
                continue

            verdict = score(case, answer, tool_calls)
            verdicts.append(verdict)
            mark = "pass" if verdict.passed else "FAIL"
            print(f"  run {attempt + 1}: {mark} ({verdict.reason})")

            records.append(
                {
                    "case_id": case.id,
                    "run": attempt + 1,
                    "passed": verdict.passed,
                    "reason": verdict.reason,
                    "tool_calls": tool_calls,
                    "answer": answer,
                }
            )

        if verdicts and all(verdict.passed for verdict in verdicts):
            reliable += 1
        if verdicts:
            print(f"  -> {stability(verdicts)}\n")
        else:
            print("  -> no successful runs\n")

    print(f"Reliable cases: {reliable}/{len(cases)}")

    RESULTS_PATH.parent.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(
            {
                "run_at": datetime.now(timezone.utc).isoformat(),
                "runs_per_case": runs,
                "reliable_cases": reliable,
                "total_cases": len(cases),
                "records": records,
            },
            indent=2,
        )
    )
    print(f"Saved to {RESULTS_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
