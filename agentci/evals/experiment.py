"""Run a candidate prompt over a dataset partition as a Phoenix experiment -> per-case scores.

API confirmation (arize-phoenix-client installed version):
- client.datasets.get_dataset(dataset=<name_or_id>) — parameter is `dataset=`, NOT `name=`
- client.experiments.run_experiment(...) returns RanExperiment (a TypedDict / dict subclass),
  NOT an object with .as_dataframe(). It has keys:
    - "task_runs": list[ExperimentRun] — TypedDicts with keys: id, dataset_example_id, output, ...
    - "evaluation_runs": list[ExperimentEvaluationRun] — dataclasses with:
        experiment_run_id, name, result (ExperimentEvaluation TypedDict with score/label/explanation)
- Metadata (split, id) comes from dataset examples (indexed by example["id"] == task_run["dataset_example_id"]).
  Dataset.examples is a list of v1.DatasetExample TypedDicts with keys: id, input, output, metadata.
- Scores are extracted by joining evaluation_runs onto task_runs via
  eval_run.experiment_run_id == task_run["id"], grouped by evaluator name.
"""
from phoenix.client import Client
from phoenix.client.resources.datasets import Dataset

from agentci import config
from agentci.evals.judges import ALL_EVALUATORS
from agentci.target.run import answer_ticket


def case_passed(scores: dict) -> bool:
    """A case passes overall iff every rubric dimension meets the threshold (D9)."""
    return all(scores.get(dim, 0.0) >= config.PASS_THRESHOLD for dim in config.RUBRIC_DIMENSIONS)


def normalize_results(raw_rows: list[dict]) -> list[dict]:
    """Attach the overall 'passed' flag to each per-case score row."""
    out = []
    for r in raw_rows:
        row = dict(r)
        row["passed"] = case_passed(r["scores"])
        out.append(row)
    return out


def _client() -> Client:
    return Client()


def run_candidate(prompt: str, dataset_name: str, split: str, experiment_name: str) -> list[dict]:
    """Run the target agent (with `prompt`) over `split` of the dataset as a Phoenix experiment.

    Returns normalized per-case rows: {"id","split","scores":{dim:float},"passed":bool}.

    API notes (no .as_dataframe() — RanExperiment is a TypedDict):
    - get_dataset uses `dataset=` kwarg (not `name=`)
    - Results extracted from ran["task_runs"] and ran["evaluation_runs"] joined on run id
    - Metadata (split/id) looked up from dataset examples via dataset_example_id
    """
    client = _client()
    # `dataset=` accepts a name string directly (DatasetIdentifier)
    dataset = client.datasets.get_dataset(dataset=dataset_name)

    # Build a lookup from example_id -> metadata for post-run join
    example_meta: dict[str, dict] = {
        ex["id"]: ex.get("metadata", {})
        for ex in dataset.examples
    }

    def task(input, metadata):  # noqa: A002 - Phoenix binds these param names
        return answer_ticket(prompt, input["question"])

    ran = client.experiments.run_experiment(
        dataset=dataset,
        task=task,
        evaluators=ALL_EVALUATORS,
        experiment_name=experiment_name,
    )

    # Index task_runs by run id for fast lookup
    task_runs_by_id: dict[str, dict] = {tr["id"]: tr for tr in ran["task_runs"]}

    # Group evaluation scores by task_run_id -> {dim: score}
    scores_by_run_id: dict[str, dict[str, float]] = {}
    for eval_run in ran["evaluation_runs"]:
        run_id = eval_run.experiment_run_id
        result = eval_run.result
        score = float(result.get("score", 0.0)) if result is not None else 0.0
        scores_by_run_id.setdefault(run_id, {})[eval_run.name] = score

    raw = []
    for run_id, task_run in task_runs_by_id.items():
        example_id = task_run["dataset_example_id"]
        md = example_meta.get(example_id, {})
        if md.get("split") != split:
            continue
        output = task_run.get("output") or {}
        raw.append({
            "id": md.get("id"),
            "split": md.get("split"),
            "answer": output.get("answer", "") if isinstance(output, dict) else "",
            "scores": {
                dim: scores_by_run_id.get(run_id, {}).get(dim, 0.0)
                for dim in config.RUBRIC_DIMENSIONS
            },
        })
    return normalize_results(raw)
