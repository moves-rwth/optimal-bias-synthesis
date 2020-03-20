import logging
import time

import stormpy


def build_model(file, hybrid=False, sylvan_threads=1, sylvan_memory=4096):
    """
    Build model from file and apply bisimulation.
    :param file: File.
    :param hybrid: If true, the model is built symbolically with BDDs and in the end converted to a sparse model.
                   If false, the model is built as a sparse model from the beginning.
    :param sylvan_threads: Number of threads to use in Sylvan library.
    :param sylvan_memory: Memory available to Sylvan.
    :return: Tuple (sparse model, prism program, property, time (s) for building , time (s) for bisimulation).
    """
    logging.debug("Build ({}) model for file {}".format("symbolic" if hybrid else "sparse", file))
    # Build model
    build_start = time.time()
    program = stormpy.parse_prism_program(file)
    prop = "R=? [F \"stable\"]"
    properties = stormpy.parse_properties(prop, program)
    assert (len(properties) == 1)

    program, properties = stormpy.preprocess_prism_program(program, properties, "")
    program = program.as_prism_program()

    if hybrid:
        # Set number of Sylvan threads to use
        stormpy.set_settings(["--sylvan:threads", str(sylvan_threads)])
        # Set memory for Sylvan
        stormpy.set_settings(["--sylvan:maxmem", str(sylvan_memory)])
        model = stormpy.build_symbolic_parametric_model(program, properties)
    else:
        model = stormpy.build_parametric_model(program, properties)
    logging.info("Built ({}) model with {} states and {} transitions.".format("symbolic" if hybrid else "sparse", model.nr_states, model.nr_transitions))
    build_end = time.time()
    time_build = build_end - build_start
    logging.info("Building model took {}s".format(time_build))

    # Bisimulation
    if hybrid:
        # Extract bisimulation quotient as sparse model
        stormpy.set_settings(["--bisimulation:quot", "sparse"])
        model = stormpy.perform_symbolic_bisimulation(model, properties)
    else:
        model = stormpy.perform_bisimulation(model, properties, stormpy.BisimulationType.STRONG)
    assert type(model) is stormpy.SparseParametricDtmc
    logging.info("Model after bisimulation: {} states and {} transitions.".format(model.nr_states, model.nr_transitions))
    time_bisim = time.time() - build_end
    logging.info("Computing bisimulation quotient took {}s".format(time_bisim))

    prop = properties[0]

    # Simplify model (by eliminating constant transitions)
    # Disabled for the moment as this leads to significantly more transitions in Herman
    if False:
        model, formula = stormpy.pars.simplify_model(model, prop.raw_formula)
        logging.info("Model after simplification: {} states and {} transitions.".format(model.nr_states, model.nr_transitions))

    return model, program, prop, time_build, time_bisim


def get_parameters(model):
    """
    Get parameters from the model.
    The parameters are sorted alphabetically.
    :param model: Model.
    :return: List of parameters.
    """
    # Parameters
    parameters = list(model.collect_probability_parameters())
    # Ensure stable ordering of variables
    parameters = sorted(parameters, key=lambda var: var.name)
    assert len(parameters) > 0
    return parameters
