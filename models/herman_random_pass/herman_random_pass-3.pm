// Herman's self stabilising algorithm as given in [KMOWZ11]
// Random pass interpretation
// Based on http://www.prismmodelchecker.org/casestudies/self-stabilisation.php

// the procotol is synchronous with no nondeterminism (a DTMC)
dtmc

// coin
const double p;

// module for process 1
module process1

	// Boolean variable for process 1
	x1 : [0..1];
    i1 : bool init false;

    [initial] (!i1) -> 0.5 : (x1'=0) & (i1'=true) + 0.5 : (x1'=1) & (i1'=true);
	[step]  (i1 & x1=x0) -> p : (x1'=1-x1) + 1-p : (x1'=x1);
	[step] (i1 & x1!=x0) -> true;
	
endmodule

// add further processes through renaming
module process2 = process1 [ x1=x2, x0=x1, i1=i2 ] endmodule
module process3 = process1 [ x1=x0, x0=x2, i1=i3 ] endmodule

formula initialized = i1 & i2 & i3;

// cost - 1 in each state (expected number of steps)
rewards "steps"
	initialized : 1;
endrewards

// formula, for use in properties: number of tokens
// (i.e. number of processes that have the same value as the process to their left)
formula num_tokens = (x1=x0?1:0)
                    +(x2=x1?1:0)
                    +(x0=x2?1:0);

// label - stable configurations (1 token)
label "stable" = num_tokens=1 & initialized;

