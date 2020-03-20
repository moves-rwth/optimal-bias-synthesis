import stormpy
import stormpy.pars


def init_solver(threshold, model, env, program=None):
    """
    Initialize PLA solver with new threshold
    :param threshold: Threshold. Can be None.
    :param model: Model.
    :param env: Environment.
    :param program: Prism program (optional).
    :return: Tuple (solver, environment)
    """
    # Set formula with current threshold
    if threshold is None:
        prop = "R=? [F \"stable\"]"
    else:
        prop = "R<={} [F \"stable\"]".format(threshold)
    formulas = stormpy.parse_properties(prop, program)
    assert len(formulas) == 1
    formula = formulas[0]
    return stormpy.pars.create_region_checker(env, model, formula.raw_formula)


def check_region(region, solver, env, vars):
    """
    Check region via PLA.
    :param region: Region.
    :param solver: PLA solver.
    :param env: Environment.
    :param vars: Variables.
    :return: PLA result.
    """
    assert solver is not None
    return solver.check_region(env, region.storm_region(vars), stormpy.pars.RegionResultHypothesis.UNKNOWN, stormpy.pars.RegionResult.UNKNOWN, True)


def get_bound_region(region, solver, env, vars, maximize):
    """
    Get bound for region via PLA.
    :param region: Region.
    :param solver: PLA solver.
    :param env: Environment.
    :param vars: Variables.
    :param maximize: Maximize if true, else minimize.
    :return: PLA result.
    """
    assert solver is not None
    result = solver.get_bound(env, region.storm_region(vars), maximize)
    assert result.is_constant()
    return result.constant_part()


def init_instantiation_checker(model, property, exact):
    """
    Initialize instantiation checker.
    :param model: Model.
    :param property: Property.
    :param exact: If true, the exact number are computed.
    :return: Instantiation checker.
    """
    if exact:
        instantiation_checker = stormpy.pars.PDtmcExactInstantiationChecker(model)
    else:
        instantiation_checker = stormpy.pars.PDtmcInstantiationChecker(model)
    instantiation_checker.specify_formula(stormpy.ParametricCheckTask(property.raw_formula, True))
    instantiation_checker.set_graph_preserving(True)
    return instantiation_checker
