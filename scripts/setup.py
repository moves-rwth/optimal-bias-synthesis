import os
import sys

from setuptools import setup

setup(
    name='optimal-bias-synthesis',
    version='1.0',
    author='M. Volk',
    author_email='matthias.volk@cs.rwth-aachen.de',
    maintainer='M. Volk',
    maintainer_email='matthias.volk@cs.rwth-aachen.de',
    url='http://moves.rwth-aachen.de',
    description='optimal-bias-synthesis - Synthesizing optimal probability values for randomized self-stabilising algorithms',
    packages=['finetuning'],
    zip_safe=False,
    install_requires=['stormpy', 'pycarl', 'matplotlib', 'z3-solver', 'sortedcontainers'],
    python_requires='>=3',
)
