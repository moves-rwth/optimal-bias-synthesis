import time
import multiprocessing
import os
import logging
import tempfile
import itertools

import stormpy
import stormpy.pars

import finetuning.analyse as analyse
import finetuning.build as build
import finetuning.pla_helper as pla_helper
from finetuning.region import Point, Interval, Region, sort_regions
from finetuning.result import Result

SOLVER = None
INST_CHECKER = None
PROGRAM = None
PROPERTY = None
ENV = None
MODEL = None
INITIAL_STATE = None
VARS = None
LOAD_TIME = None


def get_model(drn_file, solver_type=None):
    logging.debug("Get DRN model for pid {}".format(os.getpid()))
    global MODEL, VARS, INITIAL_STATE, PROPERTY, ENV, LOAD_TIME
    time_start = time.time()
    MODEL = stormpy.build_parametric_model_from_drn(drn_file)
    INITIAL_STATE = MODEL.initial_states[0]
    VARS = build.get_parameters(MODEL)
    properties = stormpy.parse_properties("R=? [F \"stable\"]")
    assert (len(properties) == 1)
    PROPERTY = properties[0]
    ENV = stormpy.Environment()
    if solver_type is not None:
        ENV.solver_environment.set_linear_equation_solver_type(solver_type)
    logging.info("Model loaded for pid {}: {} states and {} transitions.".format(os.getpid(), MODEL.nr_states, MODEL.nr_transitions))
    LOAD_TIME = time.time() - time_start


def get_load_time(i):
    global LOAD_TIME
    assert LOAD_TIME is not None
    return LOAD_TIME, os.getpid()


def gather_roots_parallel():
    logging.debug("Gather roots for pid {}".format(os.getpid()))
    global MODEL, VARS
    assert MODEL is not None
    assert VARS is not None
    time_start = time.time()
    roots = analyse.gather_roots(MODEL, VARS)
    time_end = time.time()
    return roots, VARS, time_end - time_start


def get_bound_region_parallel(region):
    logging.debug("Check region for region {} and pid {}".format(region, os.getpid()))
    global SOLVER, VARS, ENV
    assert ENV is not None
    if SOLVER is None:
        # Init solver
        logging.debug("Init solver for pid {}".format(os.getpid()))
        global MODEL, PROGRAM
        assert MODEL is not None
        SOLVER = pla_helper.init_solver(None, MODEL, ENV, PROGRAM)

    assert SOLVER is not None
    assert VARS is not None
    # Check region
    result = pla_helper.get_bound_region(region, SOLVER, ENV, VARS, False)
    return result, region


def sample_point_parallel(point, exact):
    logging.debug("Sample point {} for pid {}".format(point, os.getpid()))
    global INST_CHECKER, INITIAL_STATE, VARS, ENV
    if INST_CHECKER is None:
        logging.debug("Init instantiation checker for pid {}".format(os.getpid()))
        global MODEL, PROPERTY
        assert MODEL is not None
        assert PROPERTY is not None
        INST_CHECKER = pla_helper.init_instantiation_checker(MODEL, PROPERTY, exact)

    assert INST_CHECKER is not None
    assert INITIAL_STATE is not None
    assert ENV is not None
    assert VARS is not None
    result = INST_CHECKER.check(ENV, point.carl_valuation(VARS)).at(INITIAL_STATE)
    return result, point


class PLAParallel:
    def __init__(self, config):
        self.verbose = False
        self.no_splits = 0
        self.no_calls = 0
        self.pool = None
        self.config = config

    def sample_points(self, pool, parameters, no_samples):
        # Compute samples and pick smallest one as threshold
        size = 1.0 / (no_samples + 1)
        values = []
        for i in range(no_samples):
            val = (i + 1) * size
            values.append(val)
        # Sample points are Cartesian product of values
        d = {p: values for p in parameters}
        sample_points = []
        for p in itertools.product(*d.values()):
            point = Point({var.name: val for var, val in zip(parameters, p)})
            sample_points.append(point)
        logging.debug("Sample points: {}".format(",".join(["{}".format(p) for p in sample_points])))

        threshold = None
        best_point = None
        it = pool.starmap(sample_point_parallel, [(p, self.config.exact) for p in sample_points])
        for result, point in it:
            logging.debug("Result for point {}: {}".format(point, result))
            assert result > 0
            if threshold is None:
                threshold = result
                best_point = point
            elif threshold > result:
                threshold = result
                best_point = point
        return threshold, best_point

    def compute_satisfying_regions(self, pool, threshold, regions):
        # Compute all regions completely satisfying the threshold
        sample_regions = []
        logging.debug("Compute satisfying regions for threshold {}".format(threshold))
        lower_bound = None
        upper_bound = threshold

        self.no_calls += len(regions)
        if self.verbose:
            logging.debug("Regions: {}".format(", ".join(str(region) for region in regions)))

        it = pool.starmap(get_bound_region_parallel, [(region,) for region in regions])

        for result, region in it:
            if self.config.exact:
                result = stormpy.Rational(result)
            else:
                result = float(result)
            logging.debug("Result for {}: {}".format(region, result))

            if result > threshold:
                # Discard region
                pass
            else:
                assert result <= threshold
                # Keep region
                sample_regions.append(region)
                if lower_bound is None or result < lower_bound:
                    # New lower bound
                    lower_bound = result

        # Sample remaining regions to possibly obtain better upper bound
        best_sample = None
        it = pool.starmap(sample_point_parallel, [(region.middle(), self.config.exact) for region in sample_regions])
        for result, point in it:
            logging.debug("Result for point {}: {}".format(point, result))
            if result < upper_bound:
                # Sample is new upper bound
                upper_bound = result
                best_sample = point

        return sample_regions, best_sample, lower_bound, upper_bound

    def find_optimum(self, model_file, verbose=False):
        logging.info("Running PLA in parallel with {} processes".format(self.config.processes))
        self.verbose = verbose
        result = Result(model_file, self.config)

        start_time = time.time()
        # Build model in single process
        model, _, _, time_build, time_bisim = build.build_model(model_file, self.config.hybrid, sylvan_threads=self.config.processes, sylvan_memory=self.config.memory_limit)
        result.time_build = time_build
        result.time_bisimulation = time_bisim

        # Create temporary file for DRN export
        start_export = time.time()
        _, drn_file = tempfile.mkstemp(suffix=".drn")
        # Export model to DRN format. Each process can then load the simplified model from the file.
        stormpy.export_parametric_to_drn(model, drn_file)
        end_export = time.time()
        result.time_export = end_export - start_export
        logging.info("Exporting model took {}s".format(result.time_export))

        # Start parallelization
        with multiprocessing.Pool(self.config.processes, initializer=get_model, initargs=(drn_file, self.config.linear_equation_solver)) as pool:
            # Get loading times by trying to query all processes
            # As we cannot query each process directly, we start a number of tasks and hope that each process gets a task
            pids = set()
            max_time_load = 0
            no_tasks_time = 1
            while len(pids) < self.config.processes:
                logging.debug("Get loading times")
                it = pool.starmap(get_load_time, [(i,) for i in range(self.config.processes * no_tasks_time)])
                for time_load, pid in it:
                    if pid not in pids:
                        pids.add(pid)
                        if time_load > max_time_load:
                            max_time_load = time_load
                no_tasks_time += 1
            result.time_load = max_time_load
            logging.info("Loading model took {}s".format(result.time_load))

            # Get initial regions by computing the roots
            results = pool.apply_async(gather_roots_parallel, )
            roots, parameters, time_roots = results.get()
            result.time_roots = time_roots
            logging.info("Computing roots took {}s".format(result.time_roots))

            # Create initial intervals per parameter by splitting at roots
            initial_intervals = dict()
            for p in parameters:
                initial_interval = []
                current = 0 + self.config.eps  # 0 and 1 change graph structure
                for root in roots[p]:
                    initial_interval.append(Interval(current, root))
                    current = root
                initial_interval.append(Interval(current, 1 - self.config.eps))
                initial_intervals[p] = initial_interval
            # Create initial regions
            initial_regions = []
            for product in itertools.product(*initial_intervals.values()):
                region = {p.name: interval for p, interval in zip(parameters, product)}
                initial_regions.append(Region(region))

            if verbose:
                logging.debug("------------")
                for region in initial_regions:
                    logging.debug("Initial region {}".format(region))
                logging.debug("------------")

            # Find upper bound
            start_pla = time.time()
            logging.info("No. initial regions: {}".format(len(initial_regions)))
            upper_bound, best_sample = self.sample_points(pool, parameters, self.config.no_samples)
            logging.info("Found upper bound {} for sample {}".format(upper_bound, best_sample))
            logging.debug("Time: {:.3f}s".format(time.time() - start_time))

            if not self.config.exact:
                # Slightly increase upper bound to avoid precision issues
                upper_bound += 1e-4
            lower_bound = 0

            # Find optimum by iterating the following:
            # - use PLA (minimize) to obtain lower bounds
            # - discard all regions whose minimal result is greater than the current upper bound
            # - sample remaining regions to improve upper bound
            # - split remaining regions in half
            start_time_pla = time.time()
            start_last_iteration = start_time_pla
            iteration = 0
            if self.config.exact:
                precision = stormpy.Rational(self.config.precision)
            else:
                precision = self.config.precision
            while upper_bound - lower_bound > precision:
                iteration += 1
                if iteration == 1:
                    # Use initial regions
                    new_regions = initial_regions
                else:
                    # Split regions
                    new_regions = []
                    for region in regions:
                        # Split region into two
                        self.no_splits += 1
                        new_regions.extend(region.split(parameters))

                regions, sample, lower_bound, upper_bound = self.compute_satisfying_regions(pool, upper_bound, new_regions)
                iteration_time = time.time() - start_time_pla
                start_time_pla = time.time()
                logging.info("Iteration {}: bounds: [{}, {}], best sample: {}, {} regions remaining, {} calls, {} splits, time: {:.3f}s".format(iteration, lower_bound, upper_bound,
                                                                                                                                                best_sample, len(regions),
                                                                                                                                                self.no_calls, self.no_splits,
                                                                                                                                                iteration_time))
                if sample is not None:
                    best_sample = sample

                if verbose:
                    logging.debug("------------")
                    if self.config.exact:
                        logging.debug("Current bounds: [{}, {}], precision: {}".format(lower_bound, upper_bound, upper_bound - lower_bound))
                    else:
                        logging.debug("Current bounds: [{}, {}], precision: {:.1e}".format(lower_bound, upper_bound, upper_bound - lower_bound))
                    logging.debug("Best sample: {}".format(best_sample))
                    tmp = sort_regions(list(regions), parameters)
                    for region in tmp:
                        logging.debug("Region {}".format(region))
                    logging.debug("Time: {:.3f}s".format(time.time() - start_time_pla))
                    logging.debug("------------")

        logging.info("Remaining regions: {}, best sample: {}, {} calls, {} splits".format(len(regions), best_sample, self.no_calls, self.no_splits))

        end_pla = time.time()

        result.time_analysis = end_pla - start_pla
        result.time_total = end_pla - start_time
        result.result_ert = Interval(lower_bound, upper_bound)
        result.best_sample = best_sample
        result.result_region = sort_regions(regions, parameters)
        return result
