import logging
import itertools
import math

import stormpy

import finetuning.pla_helper as pla_helper
from finetuning.region import Point


def generate_sample_points(parameters, no_samples_per_parameter, near_bounds=False, eps=1e-10):
    """
    Generate sample points.
    :param parameters: Parameters.
    :param no_samples_per_parameter: Number of samples per parameter.
    :param near_bounds: Whether additional samples near the bounds should be generated.
    :param eps: Epsilon for minimal distance to bounds if near_bounds is set.
    :return: List of sample points.
    """
    size = 1.0 / (no_samples_per_parameter + 1)
    values = []
    if near_bounds:
        values.append(eps)
    for i in range(no_samples_per_parameter):
        val = (i + 1) * size
        values.append(val)
    if near_bounds:
        values.append(1 - eps)

    # Sample points are Cartesian product of values
    d = {p: values for p in parameters}
    sample_points = []
    for p in itertools.product(*d.values()):
        point = Point({var.name: val for var, val in zip(parameters, p)})
        sample_points.append(point)
    return sample_points


def sample(model, formula, parameters, sample_points, exact=False):
    """
    Sample model at given points.
    :param model: Model.
    :param formula: Property.
    :param parameters: Parameters.
    :param sample_points: Sample points.
    :param exact: Whether exact methods should be used.
    :return: List of tuples (sample point, sample).
    """
    # Prepare
    initial_state = model.initial_states[0]
    env = stormpy.Environment()
    inst_checker = pla_helper.init_instantiation_checker(model, formula, exact)
    # Sample all points
    samples = []
    for point in sample_points:
        result = inst_checker.check(env, point.carl_valuation(parameters)).at(initial_state)
        samples.append((point, result))
        logging.debug("Result for point {}: {}".format(point, result))

    return samples


def export_csv(csv_file, samples, parameters, max_value=math.inf):
    """
    Export sample results as CSV file.
    :param csv_file: CSV file.
    :param samples: Samples.
    :param parameters: Parameters.
    :param max_value: Maximal value for samples. Everything >max_value is set to max_value.
    """
    with open(csv_file, 'w') as f:
        # Header
        for param in parameters:
            f.write("{};".format(param))
        f.write("sample")

        # Write a row for each sample
        for point, sample in samples:
            f.write("\n")
            for param in parameters:
                f.write("{};".format(point.get_value(param)))
            val = sample if sample < max_value else max_value
            f.write("{}".format(val))
