import argparse
import os
import parser
import pprint
import random
import subprocess
import time
from shutil import rmtree
from types import SimpleNamespace

from common import (
    extract_conditions,
    extract_words,
    process_code,
)

DEFAULT_MODEL_PATH = "examples/sample_model_simple.smv"
DEFAULT_SPEC_PATH = "examples/sample_ltl_short.txt"
DEFAULT_TEMP_DIR = "NuSMV/temp"

keys = ["while", "if", "else", "elif", "not", "and", "or", ":", "True", "False"]


def parse_spec_names(spec_path):
    names = []
    with open(spec_path, "r", encoding="utf-8") as spec_file:
        for line in spec_file:
            if "LTLSPEC NAME" not in line:
                continue
            name = line.split("NAME", 1)[1].split(":=")[0].strip()
            if name:
                names.append(name)
    return names


def python2NuSMV(model_path, actions, conditions, envs, temp_dir=DEFAULT_TEMP_DIR):
    with open(model_path, "r", encoding="utf-8") as model_file:
        text = model_file.read()

    space = text.find(envs[0]) - text.find("VAR\n") - 4

    new_conds = []
    for condition in conditions:
        condition = condition.replace("True", "TRUE")
        condition = condition.replace("not", "!")
        condition = condition.replace("and", "&")
        condition = condition.replace("or", "|")
        condition = condition.replace("False", "FALSE")
        new_conds.append(condition)

    act_transition = " " * space + "next(Action) :=\n" + "  " * space + "case\n"
    for i in range(len(actions)):
        act_transition += "   " * space + new_conds[i] + " : " + actions[i] + ";\n"
    act_transition += "  " * space + "esac;\n"

    text += "\n" + act_transition

    if os.path.exists(temp_dir):
        rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    with open(f"{temp_dir}/task.smv", "w", encoding="utf-8") as task_file:
        task_file.write(text)


def verification(spec_path, spec_names, temp_dir=DEFAULT_TEMP_DIR, timeout_s=120):
    with open(f"{temp_dir}/verif.smv", "w", encoding="utf-8") as verif_file:
        with open(f"{temp_dir}/task.smv", "r", encoding="utf-8") as task_file:
            verif_file.write(task_file.read())
        verif_file.write("\n\n")
        with open(spec_path, "r", encoding="utf-8") as spec_file:
            verif_file.write(spec_file.read())

    command = f"read_model -i {temp_dir}/verif.smv \ngo\n"
    for name in spec_names:
        command += (
            f'check_ltlspec -P "{name}" -o {temp_dir}/{name}_result.txt \n'
        )
    command += "quit"

    with open(f"{temp_dir}/script.csh", "w", encoding="utf-8") as script_file:
        script_file.write(command)

    start = time.time()
    process = subprocess.Popen(
        ["NuSMV/bin/NuSMV", "-source", f"{temp_dir}/script.csh"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        process.wait(timeout_s)
    except subprocess.TimeoutExpired:
        process.kill()
        return {
            name: {"passed": False, "detail": "NuSMV verification timed out"}
            for name in spec_names
        }

    elapsed_s = time.time() - start
    results = {}
    for name in spec_names:
        result_path = f"{temp_dir}/{name}_result.txt"
        if not os.path.exists(result_path):
            results[name] = {
                "passed": False,
                "detail": "Missing NuSMV result file",
            }
            continue

        with open(result_path, "r", encoding="utf-8") as result_file:
            text = result_file.read()
        passed = "false" not in text.lower()
        results[name] = {"passed": passed, "detail": text.strip()}

    results["_elapsed_s"] = {"passed": None, "detail": f"{elapsed_s:.2f}s"}
    return results


def extract_env_vars(model_path):
    with open(model_path, "r", encoding="utf-8") as model_file:
        text_model = model_file.read()

    envs = text_model[text_model.find("VAR") + 3 :]
    envs = envs[: envs.find("Action")]
    env_list = envs.split(";")
    env_vars = []
    for env in env_list:
        env = env[: env.find(":")]
        env = env.replace("\n", "")
        env = env.replace(" ", "")
        if len(env) > 0:
            env_vars.append(env)
    return env_vars


def extract_actions(model_path):
    with open(model_path, "r", encoding="utf-8") as model_file:
        text_model = model_file.read()

    actions = text_model[text_model.find("{") + 1 : text_model.find("}")]
    act_list = actions.split(",")
    action_names = []
    for act in act_list:
        act = act.replace(" ", "")
        if len(act) > 0:
            action_names.append(act)
    return action_names


def format_verification_feedback(results):
    spec_results = {
        name: result
        for name, result in results.items()
        if not name.startswith("_")
    }
    passed = [name for name, result in spec_results.items() if result["passed"]]
    failed = [name for name, result in spec_results.items() if not result["passed"]]

    lines = [
        f"Passed {len(passed)}/{len(spec_results)} specifications.",
    ]
    if failed:
        lines.append("Failed specifications:")
        for name in failed:
            lines.append(f"- {name}: {spec_results[name]['detail']}")
    if passed:
        lines.append("Passed specifications:")
        for name in passed:
            lines.append(f"- {name}")
    return "\n".join(lines)


def score_from_results(results):
    spec_results = {
        name: result
        for name, result in results.items()
        if not name.startswith("_")
    }
    if not spec_results:
        return 0.0
    passed = sum(1 for result in spec_results.values() if result["passed"])
    return passed / len(spec_results)


def main(args, verbose=False):
    model_path = args.model_path
    spec_path = args.spec_path
    code_path = args.code_path
    temp_dir = getattr(args, "temp_dir", DEFAULT_TEMP_DIR)

    envs = extract_env_vars(model_path)
    acts = extract_actions(model_path)
    if verbose:
        print(envs, acts)

    words = keys + envs + acts

    with open(code_path, "r", encoding="utf-8") as code_file:
        code = code_file.read()

    try:
        tree = parser.suite(code).tolist()
        processed = extract_words(process_code(tree, 0), words)
    except Exception as exc:
        feedback = f"Failed to parse generated plan code: {exc}"
        if verbose:
            print(feedback)
        return {
            "score": 0.0,
            "feedback": feedback,
            "results": {},
            "conditions": [],
        }

    if verbose:
        pprint.pprint(processed)
        print()

    conditions = []
    for act in acts:
        conditions.append(extract_conditions(act, processed))

    if not any(condition.strip() for condition in conditions):
        feedback = (
            "Failed to extract controller transitions from the generated plan. "
            "Ensure the plan uses proposition-aligned API calls that map to model actions."
        )
        if verbose:
            print(feedback)
        return {
            "score": 0.0,
            "feedback": feedback,
            "results": {},
            "conditions": conditions,
        }

    python2NuSMV(model_path, acts, conditions, envs, temp_dir=temp_dir)
    spec_names = parse_spec_names(spec_path)
    results = verification(spec_path, spec_names, temp_dir=temp_dir)
    score = score_from_results(results)
    feedback = format_verification_feedback(results)

    if verbose:
        print(feedback)

    return {
        "score": score,
        "feedback": feedback,
        "results": results,
        "conditions": conditions,
    }


def compute_model_check_score(
    pred,
    model_path=DEFAULT_MODEL_PATH,
    spec_path=DEFAULT_SPEC_PATH,
    temp_dir=None,
    verbose=False,
):
    """
  Run model checking on generated Python plan code and return a score in [0, 1].

  Writes the prediction to a temporary file, invokes model-checking `main`,
  and uses the verification outcome as the optimization feedback signal.
  """
    if not pred or not str(pred).strip():
        return 0.0

    run_temp_dir = temp_dir or f"{DEFAULT_TEMP_DIR}/{random.getrandbits(128)}"
    os.makedirs(run_temp_dir, exist_ok=True)
    code_path = f"{run_temp_dir}/generated_plan.py"

    with open(code_path, "w", encoding="utf-8") as code_file:
        code_file.write(str(pred))

    args = SimpleNamespace(
        model_path=model_path,
        spec_path=spec_path,
        code_path=code_path,
        temp_dir=run_temp_dir,
    )

    try:
        outcome = main(args, verbose=verbose)
        return outcome["score"]
    except Exception as exc:
        if verbose:
            print(f"Model checking failed: {exc}")
        return 0.0
    finally:
        if temp_dir is None and os.path.exists(run_temp_dir):
            rmtree(run_temp_dir)


def evaluate_model_check(
    pred,
    model_path=DEFAULT_MODEL_PATH,
    spec_path=DEFAULT_SPEC_PATH,
    temp_dir=None,
    verbose=False,
):
    """Return score and human-readable verification feedback."""
    if not pred or not str(pred).strip():
        return 0.0, "Empty generated plan code."

    run_temp_dir = temp_dir or f"{DEFAULT_TEMP_DIR}/{random.getrandbits(128)}"
    os.makedirs(run_temp_dir, exist_ok=True)
    code_path = f"{run_temp_dir}/generated_plan.py"

    with open(code_path, "w", encoding="utf-8") as code_file:
        code_file.write(str(pred))

    args = SimpleNamespace(
        model_path=model_path,
        spec_path=spec_path,
        code_path=code_path,
        temp_dir=run_temp_dir,
    )

    try:
        outcome = main(args, verbose=verbose)
        return outcome["score"], outcome["feedback"]
    except Exception as exc:
        return 0.0, f"Model checking failed: {exc}"
    finally:
        if temp_dir is None and os.path.exists(run_temp_dir):
            rmtree(run_temp_dir)


if __name__ == "__main__":
    parser_args = argparse.ArgumentParser()
    parser_args.add_argument(
        "--model_path", type=str, default=DEFAULT_MODEL_PATH
    )
    parser_args.add_argument("--spec_path", type=str, default=DEFAULT_SPEC_PATH)
    parser_args.add_argument(
        "--code_path", type=str, default="examples/sample_plan.py"
    )
    outcome = main(parser_args.parse_args(), verbose=True)
    print(f"\nScore: {outcome['score']:.3f}")
    print(outcome["feedback"])
