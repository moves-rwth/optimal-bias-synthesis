import time
import logging
import itertools

import stormpy
import stormpy.pars

import finetuning.analyse as analyse
import finetuning.build as build
import finetuning.pla_helper as pla_helper
from finetuning.region import Point, Interval, Region, sort_regions
from finetuning.result import Result


class PLASingle:
    def __init__(self, model, config):
        self.verbose = False
        self.no_splits = 0
        self.no_calls = 0
        self.config = config
        self.model = model
        self.vars = build.get_parameters(model)
        self.initial_state = model.initial_states[0]
        self.env = stormpy.Environment()
        if config.linear_equation_solver is not None:
            self.env.solver_environment.set_linear_equation_solver_type(config.linear_equation_solver)
        self.inst_checker = None
        self.solver = None

    def sample_points(self, parameters, no_samples):
        # Compute samples and pick smallest one as threshold
        size = 1.0 / (no_samples + 2)
        values = []
        for i in range(no_samples + 1):
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
        for point in sample_points:
            result = self.inst_checker.check(self.env, point.carl_valuation(parameters)).at(self.initial_state)
            logging.debug("Result for point {}: {}".format(point, result))
            assert result > 0
            if threshold is None:
                threshold = result
                best_point = point
            elif threshold > result:
                threshold = result
                best_point = point
        return threshold, best_point

    def compute_satisfying_regions(self, threshold, regions):
        # Compute all regions completely satisfying the threshold
        sample_regions = []
        logging.debug("Compute satisfying regions for threshold {}".format(threshold))
        lower_bound = None
        upper_bound = threshold

        self.no_calls += len(regions)
        if self.verbose:
            logging.debug("Regions: {}".format(", ".join(str(region) for region in regions)))

        for region in regions:
            # Check region
            result = pla_helper.get_bound_region(region, self.solver, self.env, self.vars, False)
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
        for region in sample_regions:
            point = region.middle()
            result = self.inst_checker.check(self.env, point.carl_valuation(self.vars)).at(self.initial_state)
            logging.debug("Result for point {}: {}".format(point, result))
            if result < upper_bound:
                # Sample is new upper bound
                upper_bound = result
                best_sample = point

        return sample_regions, best_sample, lower_bound, upper_bound

    def find_optimum(self, model_file, verbose=False):
        logging.info("Running PLA on single process")
        self.verbose = verbose
        result = Result(model_file, self.config)

        # Get initial regions by computing the roots
        time_roots_start = time.time()
        roots = analyse.gather_roots(self.model, self.vars)
        result.time_roots = time.time() - time_roots_start
        logging.info("Computing roots took {}s".format(result.time_roots))

        # Create initial intervals per parameter by splitting at roots
        initial_intervals = dict()
        for p in self.vars:
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
            region = {p.name: interval for p, interval in zip(self.vars, product)}
            initial_regions.append(Region(region))

        if verbose:
            logging.debug("------------")
            for region in initial_regions:
                logging.debug("Initial region {}".format(region))
            logging.debug("------------")

        properties = stormpy.parse_properties("R=? [F \"stable\"]")
        assert len(properties) == 1
        property = properties[0]
        self.inst_checker = pla_helper.init_instantiation_checker(self.model, property, self.config.exact)

        # Find upper bound
        start_pla = time.time()
        logging.info("No. initial regions: {}".format(len(initial_regions)))
        upper_bound, best_sample = self.sample_points(self.vars, self.config.no_samples)
        logging.info("Found upper bound {} for sample {}".format(upper_bound, best_sample))
        logging.debug("Time: {:.3f}s".format(time.time() - start_pla))

        if not self.config.exact:
            # Slightly increase upper bound to avoid precision issues
            upper_bound += 1e-4
        lower_bound = 0

        self.solver = pla_helper.init_solver(None, self.model, self.env)

        # Find optimum by iterating the following:
        # - use PLA (minimize) to obtain lower bounds
        # - discard all regions whose minimal result is greater than the current upper bound
        # - sample remaining regions to improve upper bound
        # - split remaining regions in half
        start_time_pla = time.time()
        regions = initial_regions
        iteration = 0
        if self.config.exact:
            precision = stormpy.Rational(self.config.precision)
        else:
            precision = self.config.precision
        while upper_bound - lower_bound > precision:
            iteration += 1
            if iteration == 1:
                # Use initial regions
                new_regions = regions
            else:
                # Split regions
                new_regions = []
                for region in regions:
                    # Split region into two
                    self.no_splits += 1
                    new_regions.extend(region.split(self.vars))

            regions, sample, lower_bound, upper_bound = self.compute_satisfying_regions(upper_bound, new_regions)
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
                tmp = sort_regions(list(regions), self.vars)
                for region in tmp:
                    logging.debug("Region {}".format(region))
                logging.debug("Time: {:.3f}s".format(time.time() - start_time_pla))
                logging.debug("------------")

        logging.info("Remaining regions: {}, best sample: {}, {} calls, {} splits".format(len(regions), best_sample, self.no_calls, self.no_splits))

        end_pla = time.time()

        result.time_analysis = end_pla - start_pla
        result.result_ert = Interval(lower_bound, upper_bound)
        result.best_sample = best_sample
        result.result_region = sort_regions(regions, self.vars)
        return result
