import os
import time
from commom import *
import argparse
import parser
import pprint

def python2NuSMV(model_path, actions, conditions, envs):
    # actions: [stop, VP], conditions: [conditions for stop, conditions for VP]
    f = open(model_path)
    text = f.read()
    space = text.find(envs[0])-text.find('VAR\n')-4
    
    new_conds = []
    for c in conditions:
        c = c.replace('True', 'TRUE')
        c = c.replace('not', '!')
        c = c.replace('and', '&')
        c = c.replace('or', '|')
        c = c.replace('False', 'FALSE')
        new_conds.append(c)
    
    act_transition = ' '*space + 'next(Action) :=\n' + '  '*space + 'case\n'
    for i in range(len(actions)):
        act_transition += '   '*space + new_conds[i] + ' : ' + actions[i] + ';\n'
    act_transition += '  '*space + 'esac;\n'

    text += '\n' + act_transition
    os.system('rm -rf NuSMV/temp')
    os.system('mkdir NuSMV/temp')
    f = open('NuSMV/temp/task.smv', 'x')
    f.write(text)
    f.close()

def verification(spec_path, spec_names):
    # spec_names: [spec1, spec2] list of names of the defined specifications
    f_a_s = open('NuSMV/temp/verif.smv', 'x')
    f = open('NuSMV/temp/task.smv')
    f_s = open(spec_path)
    text = f.read()
    text += '\n\n' + f_s.read()
    f_a_s.write(text)
    f_a_s.close()
    f_s.close()
    f.close()
    command = 'read_model -i NuSMV/temp/verif.smv \ngo\n'
    for name in spec_names:
        cmd = 'check_ltlspec -P \"' + name + '\" -o NuSMV/temp/'+ name + '_result.txt \n' 
        command += cmd
    command += 'quit'
    f = open('NuSMV/temp/script.csh', 'x')
    f.write(command)
    f.close()
    start = time.time()
    os.system('NuSMV/bin/NuSMV -source NuSMV/temp/script.csh')
    end = time.time()
    print(end - start)

par = argparse.ArgumentParser()
par.add_argument('--model_path', type=str, default='sample_inputs/sample_model.smv')
par.add_argument('--spec_path', type=str, default='sample_inputs/sample_ltl.txt')
par.add_argument('--code_path', type=str, default='sample_inputs/sample_code.py')

keys = ['while', 'if', 'else', 'elif', 'not', 'and', 'or', ':', 'True', 'False']

def extract_env_vars(model_path):
    f = open(model_path)
    text_model = f.read()
    envs = text_model[text_model.find('VAR')+3:]
    envs = envs[:envs.find('Action')]
    env_list = envs.split(';')
    env_vars = []
    for e in env_list:
        e = e[0:e.find(':')]
        e = e.replace('\n','')
        e = e.replace(' ','')
        if len(e) > 0:
            env_vars.append(e)
    f.close()
    return env_vars

def extract_actions(model_path):
    f = open(model_path)
    text_model = f.read()
    actions = text_model[text_model.find('{')+1: text_model.find('}')]
    act_list = actions.split(',')
    actions = []
    for act in act_list:
        act = act.replace(' ', '')
        if len(act) > 0:
            actions.append(act)
    f.close()
    return actions

def main(args):
    model_path, spec_path, code_path = args.model_path, args.spec_path, args.code_path

    envs = extract_env_vars(model_path)
    acts = extract_actions(model_path)
    print(envs, acts)
    words = keys + envs + acts

    f = open(code_path)
    code = f.read()
    tree = parser.suite(code).tolist()
    # pprint.pprint(tree)
    processed = extract_words(process_code(tree, 0), words)
    pprint.pprint(processed)
    print()
    # print(prev_layer_cond(processed, len(processed)-2))
    conditions = []
    for act in acts:
        conditions.append(extract_conditions(act, processed))
    python2NuSMV(model_path, acts, conditions, envs)
    spec_names = ['spec1', 'spec2', 'spec3', 'spec4']
    verification(spec_path, spec_names)

if __name__ == '__main__':
    main(par.parse_args())