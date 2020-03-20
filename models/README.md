# Model of randomized self-stabilizing algorithms

The protocols are modeled in the [Prism language](http://www.prismmodelchecker.org/).


## Herman's algorithm
Herman's algorithm is given in the [random bit](herman_random_bit) and the [random pass](herman_random_pass) interpretation.

## Speed reducer
We consider two variants of speed reducers on top of Herman's algorithm.

The first variant has two parameters and is given as [random bit SR](herman_random_bit_speedreducer) and as [random pass SR](herman_random_pass_speedreducer).

The second variants introduces an additional parameter which governs the probability of passing the token along in the speed reducer model.
The models are given as [random bit SR2](herman_random_bit_speedreducer_2) and as [random pass SR2](herman_random_pass_speedreducer_2)
