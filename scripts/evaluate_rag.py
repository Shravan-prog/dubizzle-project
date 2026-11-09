"""Evaluate labeled inventory questions against the FastAPI chat endpoint."""
import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from main import create_app


def check(case, result, client, user):
    errors = []
    cars = result.get("referenced_cars", [])
    ids = [car["car_id"] for car in cars]
    reply = result.get("reply", "")
    if "ids" in case and sorted(ids) != sorted(case["ids"]):
        errors.append(f"Expected IDs {case['ids']}, got {ids}")
    if "unique_count" in case:
        keys = {tuple(car.get(k) for k in ("make", "model", "trim", "year", "price", "mileage_km")) for car in cars}
        if len(keys) != len(cars) or len(cars) != case["unique_count"]:
            errors.append("Unexpected result count or duplicate options")
    if "reply" in case and not re.search(case["reply"], reply, re.I):
        errors.append(f"Missing expected wording: {case['reply']}")
    for pattern in case.get("reply_all", []):
        if not re.search(pattern, reply, re.I):
            errors.append(f"Missing required answer detail: {pattern}")
    if "forbid" in case and re.search(case["forbid"], reply, re.I):
        errors.append(f"Found forbidden wording: {case['forbid']}")
    trace = result["tool_calls"]
    for name in case.get("require_model", []):
        if not any(entry.get("name") == name and entry.get("source") == "model"
                   and "error" not in entry for entry in trace):
            errors.append(f"No successful model trace for {name}")
    if case.get("require_keyword_query"):
        if not any(entry.get("name") == "search_inventory"
                   and entry.get("arguments", {}).get("query") for entry in trace):
            errors.append("Search tool did not receive a keyword query")
    for key, value in case.get("preferences", {}).items():
        if result.get("active_preferences", {}).get(key) != value:
            errors.append(f"Unexpected saved preference: {key}")
    if "lead_count" in case:
        leads = client.get("/leads", params={"user_id": user}).json()
        if leads["total"] != case["lead_count"]:
            errors.append(f"Unexpected lead count: {leads['total']}")
    return errors, ids


def run(cases, live, delay=0):
    plans = {case["question"]: case["plan"] for case in cases if "plan" in case}

    def scripted_completion(**kwargs):
        question = kwargs["messages"][-1]["content"]
        tool = SimpleNamespace(function=SimpleNamespace(
            name="search_inventory", arguments=json.dumps(plans[question])
        ))
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="", tool_calls=[tool])
        )])

    with TemporaryDirectory() as directory:
        root = Path(directory)
        shutil.copyfile(ROOT / "data/cars.csv", root / "cars.csv")
        with TestClient(create_app(root, completion=None if live else scripted_completion)) as client:
            results = []
            for case in cases:
                session = case.get("session", case["id"])
                user = case.get("user", f"eval-{session}")
                try:
                    response = client.post("/chat", json={
                        "user_id": user, "session_id": session,
                        "message": case["question"],
                    })
                    response.raise_for_status()
                    result = response.json()
                    errors, ids = check(case, result, client, user)
                    trace = [{"name": entry.get("name"), "source": entry.get("source"),
                              "arguments": entry.get("arguments"),
                              **({"reason": entry["result"]["reason"]}
                                 if entry.get("name") == "compose_grounded_response"
                                 and "reason" in entry.get("result", {}) else {})}
                             for entry in result["tool_calls"]]
                    record = dict(id=case["id"], question=case["question"], category=case["category"], errors=errors,
                                  ids=ids, reply=result["reply"], trace=trace)
                except Exception as exc:
                    record = dict(id=case["id"], category=case["category"],
                                  errors=[f"{type(exc).__name__}: evaluation request failed"])
                results.append(record)
                print(f"{'FAIL' if record['errors'] else 'PASS'} {case['id']} "
                      + "; ".join(record["errors"]), flush=True)
                if delay and live and any(entry.get("source") == "model" for entry in record.get("trace", [])):
                    time.sleep(delay)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Use the configured LLM provider")
    parser.add_argument("--dataset", type=Path, action="append", help="Question file, repeatable")
    parser.add_argument("--case", action="append", help="Run a selected case ID, repeatable")
    parser.add_argument("--delay", type=float, default=0, help="Seconds to wait after a model-backed turn")
    parser.add_argument("--output", type=Path, help="Save per-question results as JSON")
    args = parser.parse_args()
    datasets = args.dataset or [ROOT / "data/rag_eval_questions.json"]
    cases = [case for path in datasets for case in json.loads(path.read_text())]
    if args.delay < 0 or len({case["id"] for case in cases}) != len(cases):
        parser.error("Use unique question IDs and a non-negative delay")
    if args.case:
        requested = set(args.case)
        cases = [case for case in cases if case["id"] in requested]
        if {case["id"] for case in cases} != requested:
            parser.error("At least one selected case ID is missing from the dataset")
    if not args.live and any(case.get("require_model") for case in cases):
        parser.error("This dataset requires --live")
    results = run(cases, args.live, args.delay)
    passed = sum(not result["errors"] for result in results)
    mode = "live provider" if args.live else "scripted planner"
    print(f"{passed}/{len(results)} passed ({mode})")
    if args.output:
        args.output.write_text(json.dumps(dict(mode=mode, passed=passed, cases=results),
                                          indent=2, ensure_ascii=False) + "\n")
    return int(passed != len(results))


if __name__ == "__main__":
    sys.exit(main())
