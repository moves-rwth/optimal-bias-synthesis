import logging
import z3
import stormpy
import pycarl
import pycarl.cln as pc

import finetuning.build as build


def gather_roots(model, parameters):
    """
    Compute all roots of the transition probabilities.
    :param model: Model.
    :param parameters: Parameters.
    :return: Dictionary of all roots for each parameter.
    """
    roots = dict()
    for p in parameters:
        roots_p = set()
        derivatives = stormpy.pars.gather_derivatives(model, p)
        for derivative in derivatives:
            # Only one parameter is allowed per derivative
            for var in parameters:
                if var.name != p.name:
                    assert var.name not in str(derivative)

            opt = find_optimum_z3(derivative, p)
            for o in opt:
                float_opt = o.as_decimal(10)
                float_opt = float(float_opt.replace("?", ""))
                roots_p.add(float_opt)
        roots[p] = sorted(roots_p)
    return roots


def compute_rational_function(file):
    # Building
    model, program, formula = build.build_model(file)
    # Model checking
    result = stormpy.model_checking(model, formula)
    assert result.result_for_all_states
    logging.debug("Model checking results: {}".format(result))
    one = pc.FactorizedPolynomial(1)
    ratFunc = pc.FactorizedRationalFunction(pc.FactorizedPolynomial(0), one)
    for initial in model.initial_states:
        ratFunc += result.at(initial)
    div = pc.FactorizedRationalFunction(pc.FactorizedPolynomial(len(model.initial_states)), one)
    ratFunc /= div
    return ratFunc


def evaluate_rational_function(ratFunc, evaluations):
    # Evaluation
    result = []
    for evaluation in evaluations:
        # Convert values to pycarl number type
        eval = {}
        for var, val in evaluation.items():
            eval[var] = pc.Rational(val)
        value = ratFunc.evaluate(eval)
        result.append(value)
    return result


def find_optimum_z3(func, var, timeout=5000):
    logging.debug("Checking {}".format(func))
    solver = z3.Solver()
    solver.set("timeout", timeout)
    # Set variable
    z3_var = z3.Real(str(var))
    solver.add(z3_var > 0)
    solver.add(z3_var < 1)

    # Set function
    constraint_str = "(assert ( = 0 {}))".format(func.to_smt2())
    z3_constraint = z3.parse_smt2_string(constraint_str, decls={str(var): z3_var})
    solver.add(z3_constraint)

    # Solve
    result = "sat"
    optima = []
    while result == "sat":
        result = str(solver.check())
        logging.debug("Result: {}".format(result))
        if result == "sat":
            opt = solver.model()[z3_var]
            logging.debug("Model: {}".format(opt))
            optima.append(opt)
            add_constraint = z3_var != opt
            logging.debug(add_constraint)
            solver.add(add_constraint)
            # return optima
    if result == "unsat":
        return optima
    else:
        assert result == "unknown"
        logging.warning("Result of finding optimum for '{}' is 'unknown'".format(func))
        return optima


def compute_optimum(rat_func, var):
    derivative = rat_func.derive(var)
    logging.debug("Derivation of {}:\n{}".format(rat_func, derivative))
    return find_optimum_z3(derivative.numerator, var)
