// Herman's self stabilising algorithm [Her90]
// Random bit interpretation
// Taken from http://www.prismmodelchecker.org/casestudies/self-stabilisation.php

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
	[step]  (i1 & x1=x0) -> p : (x1'=0) + 1-p : (x1'=1);
	[step] (i1 & x1!=x0) -> (x1'=x0);
	
endmodule

// add further processes through renaming
module process2 = process1 [ x1=x2, x0=x1, i1=i2 ] endmodule
module process3 = process1 [ x1=x3, x0=x2, i1=i3 ] endmodule
module process4 = process1 [ x1=x4, x0=x3, i1=i4 ] endmodule
module process5 = process1 [ x1=x5, x0=x4, i1=i5 ] endmodule
module process6 = process1 [ x1=x6, x0=x5, i1=i6 ] endmodule
module process7 = process1 [ x1=x7, x0=x6, i1=i7 ] endmodule
module process8 = process1 [ x1=x8, x0=x7, i1=i8 ] endmodule
module process9 = process1 [ x1=x9, x0=x8, i1=i9 ] endmodule
module process10 = process1 [ x1=x10, x0=x9, i1=i10 ] endmodule
module process11 = process1 [ x1=x11, x0=x10, i1=i11 ] endmodule
module process12 = process1 [ x1=x12, x0=x11, i1=i12 ] endmodule
module process13 = process1 [ x1=x13, x0=x12, i1=i13 ] endmodule
module process14 = process1 [ x1=x14, x0=x13, i1=i14 ] endmodule
module process15 = process1 [ x1=x15, x0=x14, i1=i15 ] endmodule
module process16 = process1 [ x1=x16, x0=x15, i1=i16 ] endmodule
module process17 = process1 [ x1=x17, x0=x16, i1=i17 ] endmodule
module process18 = process1 [ x1=x18, x0=x17, i1=i18 ] endmodule
module process19 = process1 [ x1=x19, x0=x18, i1=i19 ] endmodule
module process20 = process1 [ x1=x20, x0=x19, i1=i20 ] endmodule
module process21 = process1 [ x1=x21, x0=x20, i1=i21 ] endmodule
module process22 = process1 [ x1=x22, x0=x21, i1=i22 ] endmodule
module process23 = process1 [ x1=x0, x0=x22, i1=i23 ] endmodule

formula initialized = i1 & i2 & i3 & i4 & i5 & i6 & i7 & i8 & i9 & i10 & i11 & i12 & i13 & i14 & i15 & i16 & i17 & i18 & i19 & i20 & i21 & i22 & i23;

// cost - 1 in each state (expected number of steps)
rewards "steps"
	initialized : 1;
endrewards

// formula, for use in properties: number of tokens
// (i.e. number of processes that have the same value as the process to their left)
formula num_tokens = (x1=x0?1:0)
                    +(x2=x1?1:0)
                    +(x3=x2?1:0)
                    +(x4=x3?1:0)
                    +(x5=x4?1:0)
                    +(x6=x5?1:0)
                    +(x7=x6?1:0)
                    +(x8=x7?1:0)
                    +(x9=x8?1:0)
                    +(x10=x9?1:0)
                    +(x11=x10?1:0)
                    +(x12=x11?1:0)
                    +(x13=x12?1:0)
                    +(x14=x13?1:0)
                    +(x15=x14?1:0)
                    +(x16=x15?1:0)
                    +(x17=x16?1:0)
                    +(x18=x17?1:0)
                    +(x19=x18?1:0)
                    +(x20=x19?1:0)
                    +(x21=x20?1:0)
                    +(x22=x21?1:0)
                    +(x0=x22?1:0);

// label - stable configurations (1 token)
label "stable" = num_tokens=1 & initialized;

