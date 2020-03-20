# Script

The synthesis algorithm is implemented as a Python script.

## Installation
The script requires the following dependencies:
- The probabilistic model checker [Storm](http://www.stormchecker.org/)
- The python bindings for Storm called [Stormpy](https://moves-rwth.github.io/stormpy/)
- The following additional Python packages will be installed automatically: `matplotlib`, `z3-solver`, `sortedcontainers`

The installation can be performed with:
```
python3 setup.py develop
```

## Usage
The script can be run with
```
python3 run.py
```

One example call to perform parameter synthesis via PLA approximation is the following:
```
python3 run.py --task approx --file ../models/herman_random_bit/herman_random_bit-3.pm --approx 1e-2
```

The script has the following configuration options which can be display with the `--help` switch.
- `--approx <error>`: Precision criterion of the resulting approximation
- `--parallel <no-cores>`: Number of cores to use for parallelization.
- `--old`: Uses the old implementation of the algorithm. This older version does not support parallelization.
- `--no-samples <number>`: Number of samples to use per parameter.
- `--exact`: Use exact rational numbers instead of floating points. This configuration prevents numerical instabilities and gives exact bounds but comes with additional computational overhead.
- `--memory <limit>`: Memory (in MB) available for symbolic BDD building.
- `-v`: Enables verbose output.
