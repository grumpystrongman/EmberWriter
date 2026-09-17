from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import generation, generation_reliability, generation_reliability_refinement, streaming_generation
from app.model_provisioning import BASELINE_CREATIVE_MODEL, has_creative_model
from app.models import ProviderConfig
from app.ollama_runtime import installed_ollama_models

DEFAULT_PROMPT = (
    "Write a direct, explicit adult intimacy scene between two consenting adults immediately after "
    "a gym workout and sauna. Keep the complete scene under 1300 words. Use direct anatomical and "
    "sexual action rather than fade-to-black or euphemistic summary; include penetration/genitalia and "
    "make it unambiguous that both participants reach orgasm. Decide the sequence yourself and finish "
    "with a clean immediate aftermath."
)
DEFAULT_CONTEXT = (
    "Both participants are established consenting adults. The requested scene starts immediately after "
    "their workout and sauna in a private setting. Stay focused on the two participants and the requested "
    "encounter; do not introduce unrelated plot exposition or additional characters."
)


@dataclass
class RunResult:
    run: int
    passed: bool
    model: str
    word_count: int
    maximum_words: int | None
    below_ceiling: bool
    direct_delivery: bool
    quality_ok: bool
    ending_complete: bool
    output_sha256: str
    failure: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run EmberWriter's real Studio generation stack repeatedly against local Ollama and score "
            "contract reliability without printing or saving generated prose."
        )
    )
    parser.add_argument("--runs", type=int, default=10, help="Number of real generations (default: 10)")
    parser.add_argument(
        "--required-pass-rate",
        type=float,
        default=0.90,
        help="Required passing fraction (default: 0.90)",
    )
    parser.add_argument("--prompt", default="", help="Override the acceptance prompt")
    parser.add_argument("--prompt-file", default="", help="Read the acceptance prompt from a UTF-8 file")
    parser.add_argument("--model", default=BASELINE_CREATIVE_MODEL, help="Preferred local Ollama model")
    parser.add_argument(
        "--no-pull",
        action="store_true",
        help="Do not automatically pull the baseline creative model when none is installed",
    )
    return parser.parse_args()


def load_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8").strip()
    if args.prompt:
        return args.prompt.strip()
    return DEFAULT_PROMPT


def ensure_creative_model(preferred: str, *, allow_pull: bool) -> None:
    ollama = shutil.which("ollama")
    if not ollama:
        raise RuntimeError("Ollama is not installed or is not on PATH")

    async def inspect() -> list[str]:
        return await installed_ollama_models("http://127.0.0.1:11434")

    installed = asyncio.run(inspect())
    if has_creative_model(installed):
        return
    if not allow_pull:
        raise RuntimeError(
            "No creative/RP writing model is installed. Re-run without --no-pull to provision one."
        )

    print(f"No creative/RP model detected. Pulling {preferred} ...", flush=True)
    completed = subprocess.run([ollama, "pull", preferred], check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"ollama pull failed for {preferred} (exit {completed.returncode})")

    installed = asyncio.run(inspect())
    if not has_creative_model(installed):
        raise RuntimeError("Ollama pull completed but no recognized creative/RP model is installed")


async def run_once(index: int, prompt: str, preferred_model: str) -> RunResult:
    contract = generation_reliability.parse_scene_length(prompt, "inferno")
    floor = generation.scene_word_floor(prompt, "inferno")
    messages = generation.build_messages(
        "write",
        prompt,
        DEFAULT_CONTEXT,
        heat_level="inferno",
        min_scene_words=floor,
    )
    provider = ProviderConfig(
        provider="ollama",
        base_url="http://127.0.0.1:11434",
        model=preferred_model,
    )

    async def discard_delta(_: str) -> None:
        return None

    async def discard_status(_: str) -> None:
        return None

    try:
        text = await streaming_generation.generate_complete_prose_streamed(
            provider,
            messages,
            min_words=floor,
            on_delta=discard_delta,
            on_status=discard_status,
        )
    except Exception as exc:  # acceptance harness must record terminal failures rather than abort all runs
        return RunResult(
            run=index,
            passed=False,
            model=provider.model,
            word_count=0,
            maximum_words=contract.max_words,
            below_ceiling=False,
            direct_delivery=False,
            quality_ok=False,
            ending_complete=False,
            output_sha256="",
            failure=f"{type(exc).__name__}: {exc}",
        )

    words = len(text.split())
    below_ceiling = contract.max_words is None or words < contract.max_words
    explicit_failure = generation_reliability_refinement.explicit_delivery_failure(prompt, text)
    quality_failure = generation_reliability._hard_quality_failure(text)
    ending_complete = not generation.looks_abrupt_ending(text)
    marker_leak = (
        generation.SCENE_COMPLETE_MARKER in text or generation.SCENE_CONTINUE_MARKER in text
    )

    failures: list[str] = []
    if not below_ceiling:
        failures.append(f"word ceiling violated: {words} >= {contract.max_words}")
    if explicit_failure:
        failures.append(explicit_failure)
    if quality_failure:
        failures.append(quality_failure)
    if not ending_complete:
        failures.append("ending appears abrupt or incomplete")
    if marker_leak:
        failures.append("internal scene marker leaked into manuscript")

    return RunResult(
        run=index,
        passed=not failures,
        model=provider.model,
        word_count=words,
        maximum_words=contract.max_words,
        below_ceiling=below_ceiling,
        direct_delivery=not explicit_failure,
        quality_ok=not quality_failure,
        ending_complete=ending_complete,
        output_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        failure="; ".join(failures),
    )


async def run_suite(args: argparse.Namespace, prompt: str) -> list[RunResult]:
    results: list[RunResult] = []
    for index in range(1, args.runs + 1):
        print(f"Acceptance run {index}/{args.runs} ...", flush=True)
        result = await run_once(index, prompt, args.model)
        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        detail = f"{result.word_count} words" if result.word_count else result.failure
        print(f"  {status}: {detail} | model={result.model}", flush=True)
    return results


def write_report(args: argparse.Namespace, results: list[RunResult]) -> Path:
    output_dir = REPO_ROOT / ".ember" / "acceptance"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "writing-acceptance-latest.json"
    passed = sum(result.passed for result in results)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "runs": len(results),
        "passed": passed,
        "pass_rate": passed / len(results) if results else 0.0,
        "required_pass_rate": args.required_pass_rate,
        "results": [asdict(result) for result in results],
        "note": "Generated manuscript prose is intentionally neither printed nor stored.",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if not 0 < args.required_pass_rate <= 1:
        raise SystemExit("--required-pass-rate must be > 0 and <= 1")

    prompt = load_prompt(args)
    if not prompt:
        raise SystemExit("Acceptance prompt is empty")

    ensure_creative_model(args.model, allow_pull=not args.no_pull)
    results = asyncio.run(run_suite(args, prompt))
    report_path = write_report(args, results)

    passed = sum(result.passed for result in results)
    required = math.ceil(args.runs * args.required_pass_rate)
    print("")
    print(f"Acceptance result: {passed}/{args.runs} passed; required {required}/{args.runs}.")
    print(f"Metrics report: {report_path}")
    if passed < required:
        print("ACCEPTANCE FAILED")
        return 1
    print("ACCEPTANCE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
