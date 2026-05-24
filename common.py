import os
import subprocess
from shutil import rmtree
import re
import random
import numpy as np

def process_code(tree, layer):
    if tree[0] < 257:
        return [[layer] + [tree[1]]]
    processed = []
    layer = layer + 1 if len(tree)>2 else layer
    for t in tree[1:]:
        processed += process_code(t, layer)
    return processed

def match_proposition(tree_node, words, correspondance):
    # determine which proposition a function is matched to
    t = tree_node[1]
    for w in words:
        if correspondance(t, w):
            return tree_node
    return None

def extract_words(tree, words):
    def correspondance(a, b):
        return a == b
    extracted = []
    for t in tree:
        matched = match_proposition(t, words, correspondance)
        if matched != None:
            extracted.append(matched)
    return extracted

def prev_layer_cond(words, action_idx):
    current = words[action_idx][0]
    conditions = set()
    idx = action_idx
    while idx >= 0:
        idx -= 1
        if words[idx][1] == ':' and current > words[idx][0] + 1:
            current = words[idx][0]
            idx -= 1
            cond = []
            if words[idx][1] == 'else':
                start = idx
                while words[start][1] != 'if':
                    start -= 1
                if_idx = start
                while start < idx:
                    while words[start][1] not in ['if', 'elif', 'else']:
                        start += 1
                    cond = []
                    start += 1
                    while words[start][1] != ':':
                        cond.append(words[start][1])
                        start += 1
                    if len(cond) > 0:
                        conditions.add('not (' + ' '.join(cond) + ')')
                idx = if_idx
            else:
                while words[idx][0] != current and idx >= 0:
                    cond.append(words[idx][1])
                    idx -= 1
                cond.reverse()
                if len(cond) == 0:
                    cond = ['True']
                conditions.add(' '.join(cond))
    return conditions

def extract_conditions(action, words):
    conditions = []
    for i in range(len(words)):
        if words[i][1] == action:
            cond = prev_layer_cond(words, i)
            cond_str = []
            for c in cond:
                cond_str.append('('+c+')')
            cond_str_ = ' and '.join(cond_str)
            conditions.append(cond_str_)
    return ' or '.join(conditions)

####$ TRAIN SETTINGS #####
BATCH_SIZE = 3
MAX_STEPS = 20
NUM_WORKERS = 20

##### PATH AND CONFIGS #####

os.environ["OPENAI_API_KEY"] = "PLEASE INPUT YOUR API KEY HERE"
AD_MODEL_PATH = 'examples/sample_model.smv'
AD_SPECS_PATH = 'examples/sample_ltl_short.txt'

with open(AD_SPECS_PATH, 'r', encoding='utf-8') as file:
        specs = file.read()

BASELINE_PROMPT = "Complete the following NuSMV solving the driving task. Ensure the NuSMV model adheres to the correct syntax and logical specifications for the driving task."
#BASELINE_PROMPT = "Complete the following NuSMV solving the driving task."
EVAL_FN_DESCRIPTION = f"Ratio between fulfilled specifications and total specifications. Specifications, written in temporal logic:\n\n{specs}\n\nIf the evaluator cannot parse the answer, the score will be set to 0."

MODEL_CHECK_MODEL_PATH = "examples/sample_model_simple.smv"
MODEL_CHECK_SPEC_PATH = "examples/sample_ltl_short.txt"

with open(MODEL_CHECK_SPEC_PATH, "r", encoding="utf-8") as file:
    model_check_specs = file.read()

MODEL_CHECK_EVAL_FN_DESCRIPTION = (
    "Ratio between fulfilled specifications and total specifications after NuSMV model checking. "
    "The generated Python plan is parsed into controller transitions and verified against:\n\n"
    f"{model_check_specs}\n\n"
    "If the plan cannot be parsed or verification fails to run, the score is 0."
)

##### UTILS #####

def _load_model_checking():
    import importlib.util
    from pathlib import Path

    module_path = Path(__file__).resolve().parent / "model-checking.py"
    spec = importlib.util.spec_from_file_location("model_checking", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compute_model_check_score(pred, verbose=False):
    model_checking = _load_model_checking()
    return model_checking.compute_model_check_score(
        pred,
        model_path=MODEL_CHECK_MODEL_PATH,
        spec_path=MODEL_CHECK_SPEC_PATH,
        verbose=verbose,
    )


def evaluate_model_check(pred, verbose=False):
    model_checking = _load_model_checking()
    return model_checking.evaluate_model_check(
        pred,
        model_path=MODEL_CHECK_MODEL_PATH,
        spec_path=MODEL_CHECK_SPEC_PATH,
        verbose=verbose,
    )

def compute_spec_score(pred):
    """
    pred_input : str (AD_model + controller)
    return : float (specification score)
    """
    hash = random.getrandbits(128)
    question_path = f"NuSMV/temp/{hash}"

    if os.path.exists(question_path):
        rmtree(question_path)

    os.mkdir(question_path)

    # READ SPECS
    spec_file = open(AD_SPECS_PATH)
    specs = []
    while True:
        spec = spec_file.readline()
        if len(spec) > 1:
            specs.append(spec)
        if len(spec) == 0:
            break
    spec_file.close()

    # MERGE AUTOMATON AND SPEC TO A FILE
    f_a_s = open(f'{question_path}/verif.smv', 'x')
    f_s = open(AD_SPECS_PATH)
    if "MODULE main" not in pred:
        with open(AD_MODEL_PATH, 'r', encoding='utf-8') as file:
            model = file.read()
        aut = model + '\n\n' + pred + '\n\n'
    else:
        aut = pred + '\n\n'
    spc = f_s.read()
    f_a_s.write(aut + spc)
    f_s.close()
    f_a_s.close()

    #print(aut)
    
    # BUILD COMMAND FILE
    command = f'read_model -i {question_path}/verif.smv \ngo\n'
    idx = 1
    for spec in specs:
        name = '\"' + spec.split(' ')[2] + '\"'
        cmd = 'check_ltlspec -P ' + name + f' -o {question_path}/result' + str(idx) + '.txt \n' 
        command += cmd
        idx += 1
    command += 'quit'
    f = open(f'{question_path}/script.csh', 'x')
    f.write(command)
    f.close()

    # TRY TO RUN COMMAND
    p = subprocess.Popen(
        ['NuSMV/bin/NuSMV', '-source', f'{question_path}/script.csh'], 
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT
    )
    try:
        p.wait(5)
    except subprocess.TimeoutExpired:
        p.kill()
        #print(f"Error running script")
        print(f"Example score:{0}", flush=True)
        rmtree(question_path)
        return 0

    # COUNT RESULTS
    files = os.listdir(question_path)
    results = []
    for f in files:
        if 'result' in f:
            results.append(question_path + "/" + f)
    result_text = ''

    #result_bools = {}

    for r in results:
        f = open(r)
        text = f.read()

        #result_bools[f.name.split("/")[-1]] = (text.count('false') + 1) % 2 # 1 if succeeds 0 otherwise

        result_text += text + '\n\n'
    num_fails = result_text.count('false')

    rmtree(question_path)

    score = (len(results) - num_fails) / len(results)
    #print(f"Example score:{score}, bools:{result_bools}", flush=True)

    
    return score

def clean_output(text):
    """
    Extracts content between triple backticks (```) in the given string.
    Returns the last captured text blocks, removing nusmv text.
    This was designed to be used with GPT-4o
    """

    pattern = r'```(.*?)```'
    patterns = re.findall(pattern, text, re.DOTALL)
    if len(patterns) > 0:
        return patterns[-1].replace("nusmv", "")
    
    match = re.search(r'NUSVM:\s*(.*)', text, re.DOTALL)
    if match:
        return match.group(1) 

    return text

def set_seed(seed):
    np.random.seed(seed)
    random.seed(seed)

def load_data():
    data = ['Turn right at the park exit.',
            'Stop at the gas station.',
            'Move forward at the traffic light.',
            'Turn right at the green left-turn light.',
            'Move forward at the railroad crossing.',
            'Turn left onto the service road.',
            'Move forward at the green left-turn light.',
            'Stop at the railroad crossing.',
            'Turn left at the construction site.',
            'Stop at the loading dock.',
            'Stop at the toll booth.',
            'Turn left at the driveway.',
            'Move forward through the school zone.',
            'Move forward through the roundabout.',
            'Turn left at the intersection.',
            'Turn left at the green left-turn light.',
            'Stop at the pedestrian crossing.',
            'Stop at the next traffic signal.',
            'Turn right at the roundabout.',
            'Turn right at the exit ramp.',

            'Stop at the intersection.',
            'Move forward on the city street.',
            'Turn right at the bus stop.',
            'Turn left at the bus stop.',
            'Move forward after the rest area.',
            'Turn right into the neighborhood.',
            'Turn left at the stop sign.',
            'Turn right at the stop sign.',
            'Stop at the yield sign.',
            'Turn left at the exit ramp.',
            'Turn left at the park exit.',
            'Turn left at the roundabout.',
            'Move forward at the green traffic light.',
            'Move forward on the highway.',
            'Turn left at the traffic light.',
            'Move forward at the next checkpoint.',
            'Turn right at the next street.',
            'Stop at the school crossing.',
            'Move forward at the yield sign.',
            'Stop at the next checkpoint.',

            'Turn right at the driveway.',
            'Turn left into the parking lot.',
            'Turn left at the next street.',
            'Turn left into the neighborhood.',
            'Turn left after the toll booth.',
            'Move forward at the toll booth.',
            'Stop at the rest area.',
            'Move forward on the main road.',
            'Turn right at the intersection.',
            'Turn right at the traffic light.',
            'Turn right onto the service road.',
            'Turn left at the next highway junction.',
            'Turn right at the construction site.',
            'Move forward on the ramp.',
            'Move forward through the construction site.',
            'Turn right into the parking lot.',
            'Move forward at the intersection.',
            'Move forward at the park entrance.',
            'Turn right at the next highway junction.',
            'Turn right after the toll booth.']

    with open(AD_MODEL_PATH, 'r', encoding='utf-8') as file:
        nusmv = file.read()
    data = [f"NUSMV: {nusmv}\n\nTask: " + d for d in data]

    return data[:len(data)//3], data[len(data)//3:2*len(data)//3], data[2*len(data)//3:]

def load_data_c1():

    train = [
        "Turn right at the park exit, then stop at the gas station.",
        "Move forward at the traffic light, then turn right at the green left-turn light.",
        "Move forward at the railroad crossing, then turn left onto the service road.",
        "Move forward at the green left-turn light, then stop at the railroad crossing.",
        "Turn left at the construction site, then stop at the loading dock.",
        "Stop at the toll booth, then turn left at the driveway.",
        "Move forward through the school zone, then move forward through the roundabout.",
        "Turn left at the intersection, then turn left at the green left-turn light.",
        "Stop at the pedestrian crossing, then stop at the next traffic signal.",
        "Turn right at the roundabout, then turn right at the exit ramp.",
        "Turn left at the service road, then move forward at the traffic light.",
        "Stop at the gas station, then turn right at the exit ramp.",
        "Move forward through the roundabout, then stop at the pedestrian crossing.",
        "Turn right at the park exit, then move forward through the school zone.",
        "Turn left at the driveway, then stop at the next traffic signal.",
        "Stop at the railroad crossing, then turn left at the construction site.",
        "Turn left at the green left-turn light, then stop at the toll booth.",
        "Move forward at the green left-turn light, then turn right at the roundabout.",
        "Turn right at the exit ramp, then stop at the loading dock.",
        "Stop at the pedestrian crossing, then move forward at the traffic light."
    ]


    val  = [
        "Stop at the intersection, then move forward on the city street.",
        "Turn right at the bus stop, then turn left at the bus stop.",
        "Move forward after the rest area, then turn right into the neighborhood.",
        "Turn left at the stop sign, then turn right at the stop sign.",
        "Stop at the yield sign, then turn left at the exit ramp.",
        "Turn left at the park exit, then turn left at the roundabout.",
        "Move forward at the green traffic light, then move forward on the highway.",
        "Turn left at the traffic light, then move forward at the next checkpoint.",
        "Turn right at the next street, then stop at the school crossing.",
        "Move forward at the yield sign, then stop at the next checkpoint.",
        "Stop at the school crossing, then turn right at the next street.",
        "Turn left at the exit ramp, then stop at the intersection.",
        "Turn right into the neighborhood, then move forward at the green traffic light.",
        "Turn left at the roundabout, then move forward on the highway.",
        "Move forward on the city street, then turn left at the traffic light.",
        "Turn right at the stop sign, then stop at the yield sign.",
        "Move forward after the rest area, then turn left at the park exit.",
        "Turn left at the bus stop, then move forward at the yield sign.",
        "Move forward at the next checkpoint, then stop at the next checkpoint.",
        "Turn right at the bus stop, then move forward at the green traffic light."
    ]


    test  = [
        "Turn right at the driveway, then turn left into the parking lot.",
        "Turn left at the next street, then turn left into the neighborhood.",
        "Turn left after the toll booth, then move forward at the toll booth.",
        "Stop at the rest area, then move forward on the main road.",
        "Turn right at the intersection, then turn right at the traffic light.",
        "Turn right onto the service road, then turn left at the next highway junction.",
        "Turn right at the construction site, then move forward on the ramp.",
        "Move forward through the construction site, then turn right into the parking lot.",
        "Move forward at the intersection, then move forward at the park entrance.",
        "Turn right at the next highway junction, then turn right after the toll booth.",
        "Turn left into the parking lot, then move forward on the main road.",
        "Move forward at the toll booth, then turn right at the intersection.",
        "Turn left at the next street, then stop at the rest area.",
        "Turn right at the traffic light, then turn right onto the service road.",
        "Move forward on the ramp, then turn left at the next highway junction.",
        "Turn left into the neighborhood, then turn right at the construction site.",
        "Move forward at the park entrance, then move forward at the intersection.",
        "Turn right into the parking lot, then turn right at the driveway.",
        "Turn right after the toll booth, then move forward through the construction site.",
        "Turn left after the toll booth, then move forward at the intersection."
    ]

    with open(AD_MODEL_PATH, 'r', encoding='utf-8') as file:
        nusmv = file.read()

    train = [f"NUSMV: {nusmv}\n\nTask: " + d for d in train]
    test = [f"NUSMV: {nusmv}\n\nTask: " + d for d in test]
    val = [f"NUSMV: {nusmv}\n\nTask: " + d for d in val]

    return train, val, test

def load_data_c2():
    train  = [
        "Turn right at the park exit, then stop at the gas station, then move forward at the traffic light.",
        "Turn right at the green left-turn light, then move forward at the railroad crossing, then turn left onto the service road.",
        "Move forward at the green left-turn light, then stop at the railroad crossing, then turn left at the construction site.",
        "Stop at the loading dock, then stop at the toll booth, then turn left at the driveway.",
        "Move forward through the school zone, then move forward through the roundabout, then turn left at the intersection.",
        "Turn left at the green left-turn light, then stop at the pedestrian crossing, then stop at the next traffic signal.",
        "Turn right at the roundabout, then turn right at the exit ramp, then stop at the gas station.",
        "Turn left onto the service road, then move forward at the traffic light, then turn right at the exit ramp.",
        "Stop at the railroad crossing, then turn left at the construction site, then stop at the loading dock.",
        "Move forward through the roundabout, then stop at the pedestrian crossing, then move forward at the traffic light.",
        "Turn right at the park exit, then move forward through the school zone, then turn left at the driveway.",
        "Turn left at the driveway, then stop at the next traffic signal, then move forward through the school zone.",
        "Stop at the gas station, then turn right at the green left-turn light, then move forward at the railroad crossing.",
        "Move forward at the green left-turn light, then stop at the toll booth, then turn left at the construction site.",
        "Turn right at the roundabout, then turn left at the intersection, then move forward through the roundabout.",
        "Stop at the pedestrian crossing, then move forward at the next traffic signal, then turn right at the exit ramp.",
        "Turn left at the green left-turn light, then move forward through the school zone, then stop at the railroad crossing.",
        "Move forward at the traffic light, then turn right at the exit ramp, then stop at the loading dock.",
        "Stop at the toll booth, then turn left onto the service road, then move forward at the traffic light.",
        "Turn left at the intersection, then turn right at the roundabout, then move forward at the railroad crossing."
    ]

    val = [
        "Stop at the intersection, then move forward on the city street, then turn right at the bus stop.",
        "Turn left at the bus stop, then move forward after the rest area, then turn right into the neighborhood.",
        "Turn left at the stop sign, then turn right at the stop sign, then stop at the yield sign.",
        "Turn left at the exit ramp, then turn left at the park exit, then turn left at the roundabout.",
        "Move forward at the green traffic light, then move forward on the highway, then turn left at the traffic light.",
        "Move forward at the next checkpoint, then turn right at the next street, then stop at the school crossing.",
        "Move forward at the yield sign, then stop at the next checkpoint, then turn right into the neighborhood.",
        "Turn left at the bus stop, then move forward on the city street, then stop at the yield sign.",
        "Stop at the school crossing, then turn right at the next street, then move forward at the green traffic light.",
        "Turn left at the park exit, then stop at the intersection, then move forward on the highway.",
        "Turn right at the bus stop, then stop at the next checkpoint, then turn left at the roundabout.",
        "Move forward on the city street, then turn left at the traffic light, then stop at the school crossing.",
        "Turn right at the stop sign, then stop at the yield sign, then move forward at the green traffic light.",
        "Move forward after the rest area, then turn left at the park exit, then turn right into the neighborhood.",
        "Turn left at the bus stop, then move forward at the yield sign, then turn right at the next street.",
        "Turn left at the traffic light, then move forward at the next checkpoint, then stop at the next checkpoint.",
        "Turn right at the bus stop, then move forward at the green traffic light, then move forward on the highway.",
        "Move forward at the next checkpoint, then stop at the intersection, then move forward on the city street.",
        "Turn left at the roundabout, then move forward on the highway, then turn right at the stop sign.",
        "Turn left at the exit ramp, then turn right into the neighborhood, then move forward at the next checkpoint."
    ]

    test = [
        "Turn right at the driveway, then turn left into the parking lot, then turn left at the next street.",
        "Turn left into the neighborhood, then turn left after the toll booth, then move forward at the toll booth.",
        "Stop at the rest area, then move forward on the main road, then turn right at the intersection.",
        "Turn right at the traffic light, then turn right onto the service road, then turn left at the next highway junction.",
        "Turn right at the construction site, then move forward on the ramp, then move forward through the construction site.",
        "Turn right into the parking lot, then move forward at the intersection, then move forward at the park entrance.",
        "Turn right at the next highway junction, then turn right after the toll booth, then move forward at the toll booth.",
        "Move forward through the construction site, then turn left into the neighborhood, then turn right at the traffic light.",
        "Turn left at the next street, then turn right at the construction site, then stop at the rest area.",
        "Move forward at the intersection, then move forward at the park entrance, then turn right at the driveway.",
        "Turn left after the toll booth, then turn right onto the service road, then turn left at the next highway junction.",
        "Turn right at the traffic light, then turn right at the next highway junction, then move forward on the main road.",
        "Move forward on the ramp, then move forward through the construction site, then turn left at the next street.",
        "Turn right at the driveway, then stop at the rest area, then move forward at the park entrance.",
        "Turn left into the parking lot, then turn right into the parking lot, then move forward on the main road.",
        "Turn right at the intersection, then move forward on the ramp, then turn left into the neighborhood.",
        "Turn right at the construction site, then turn right at the traffic light, then move forward at the toll booth.",
        "Move forward at the intersection, then turn right at the next highway junction, then move forward through the construction site.",
        "Turn left at the next highway junction, then turn right after the toll booth, then turn left after the toll booth.",
        "Move forward on the main road, then turn right at the driveway, then move forward at the park entrance."
    ]


    with open(AD_MODEL_PATH, 'r', encoding='utf-8') as file:
        nusmv = file.read()

    train = [f"NUSMV: {nusmv}\n\nTask: " + d for d in train]
    test = [f"NUSMV: {nusmv}\n\nTask: " + d for d in test]
    val = [f"NUSMV: {nusmv}\n\nTask: " + d for d in val]

    return train, val, test


