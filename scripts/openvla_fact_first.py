"""Candidate carrier: initial fact before the unchanged action question."""
from pathlib import Path
from openvla_spatial_4bit import Policy, sha
from openvla_question_context import PREFIX, SUFFIX

def fact_first(prompt):
    if not prompt.startswith(PREFIX) or not prompt.endswith(SUFFIX):
        raise RuntimeError('Unexpected upstream action prompt.')
    body = prompt[len(PREFIX):-len(SUFFIX)]
    if '\n' not in body:
        return prompt
    question, fact = body.split('\n', 1)
    if not question or not fact or '\n' in fact:
        raise RuntimeError('One original question and one fact line required.')
    return 'In:\n' + fact + ' What action should the robot take to ' + question + SUFFIX

class FactFirstProcessor:
    def __init__(self, delegate):
        self.delegate = delegate
    def __call__(self, prompt, image):
        return self.delegate(fact_first(prompt), image)
    def __getattr__(self, name):
        return getattr(self.delegate, name)

class FactFirstPolicy(Policy):
    def __init__(self):
        super().__init__()
        self.processor = FactFirstProcessor(self.processor)
        self.runtime['text_variant'] = {'name': 'fact_first_v1', 'variant_sha256': sha(Path(__file__)),
            'N_prompt_unchanged': True, 'initial_fact_before_action_question': True}
