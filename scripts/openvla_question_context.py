"""A declared text-only variant: close the native action question before facts."""
from __future__ import annotations
from pathlib import Path

from openvla_spatial_4bit import Policy, sha

PREFIX = 'In: What action should the robot take to '
SUFFIX = '?\nOut:'


def question_then_fact(prompt):
    if not prompt.startswith(PREFIX) or not prompt.endswith(SUFFIX):
        raise RuntimeError('Unexpected upstream OpenVLA prompt.')
    body = prompt[len(PREFIX):-len(SUFFIX)]
    if '\n' not in body:
        return prompt
    question, fact = body.split('\n', 1)
    if not question or not fact or '\n' in fact:
        raise RuntimeError('Exactly one original instruction and one fact line are required.')
    return PREFIX + question + '?\n' + fact + '\nOut:'


class QuestionThenFactProcessor:
    def __init__(self, delegate):
        self.delegate = delegate

    def __call__(self, prompt, image):
        return self.delegate(question_then_fact(prompt), image)

    def __getattr__(self, name):
        return getattr(self.delegate, name)


class ContextPolicy(Policy):
    def __init__(self):
        super().__init__()
        self.processor = QuestionThenFactProcessor(self.processor)
        self.runtime['text_variant'] = {'name': 'question_then_fact_v1',
                                       'variant_sha256': sha(Path(__file__)),
                                       'N_prompt_unchanged': True,
                                       'appended_fact_outside_action_question': True}
