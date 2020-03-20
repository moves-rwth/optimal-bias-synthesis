import time
import logging

import stormpy
import stormpy.pars

import finetuning.analyse as analyse
import finetuning.build as build
import finetuning.pla_helper as pla_helper
from finetuning.region import Region, Interval, sort_regions


class PLAOld:
    """
    Old implementation of PLA approximation algorithm
    """
    def __init__(self, model, program, config, verbose=False):
        self.model = model
        self.program = program
        self.config = config
        self.verbose = verbose
        vars = build.get_parameters(model)
        assert len(vars) == 1
        self.var = vars[0]
        self.env = stormpy.Environment()
        if config.linear_equation_solver is not None:
            self.env.solver_environment.set_linear_equation_solver_type(config.linear_equation_solver)
        self.checker = None
        self.roots = set()
        self.no_calls = 0
        self.time_calls = 0
        self.no_splits = 0

    def check(self, region):
        self.no_calls += 1
        start_time = time.time()
        result = pla_helper.check_region(region, self.checker, self.env, [self.var])
        self.time_calls += time.time() - start_time
        return result

    def compute_satisfying_regions(self, threshold, regions, intervalSize, env):
        # Compute all regions completely satisfying the threshold
        satRegions = []
        unknownRegions = []
        self.checker = pla_helper.init_solver(threshold, self.model, self.env, self.program)
        while len(regions) > 0:
            # Compute result for next region
            region = regions.pop(0)

            result = self.check(region)
            if result == stormpy.pars.RegionResult.ALLSAT:
                # Keep region
                satRegions.append(region)
            elif result == stormpy.pars.RegionResult.ALLVIOLATED:
                # Discard region
                pass
            elif result == stormpy.pars.RegionResult.EXISTSBOTH or result == stormpy.pars.RegionResult.CENTERSAT or result == stormpy.pars.RegionResult.CENTERVIOLATED:
                if region.intervals[self.var.name].upper - region.intervals[self.var.name].lower > intervalSize:
                    # Split region into two
                    self.no_splits += 1
                    regions.extend(region.split([self.var]))
                else:
                    if result == stormpy.pars.RegionResult.CENTERVIOLATED:
                        # Region is still unknown
                        unknownRegions.append(region)
                    else:
                        # At least one point satisfies the threshold
                        satRegions.append(region)
            else:
                # Unknown region
                assert False

        return satRegions, unknownRegions

    def compute_optima_via_pla(self):
        # Model checking via PLA
        lowerBound = 0
        upperBound = 1
        intervalSize = 0.1
        startTimePLAInit = time.time()
        # Compute initial regions
        initialRegions = []
        time_roots_start = time.time()
        self.roots = analyse.gather_roots(self.model, [self.var])[self.var]
        time_roots = time.time() - time_roots_start
        logging.info("Computing roots took {}s".format(time_roots))
        sortedRoots = sorted(self.roots)
        current = 0 + self.config.eps  # 0 and 1 change graph structure
        for root in sortedRoots:
            initialRegions.append(Region.from_single_var(self.var.name, current, root))
            current = root
        initialRegions.append(Region.from_single_var(self.var.name, current, 1 - self.config.eps))

        if self.verbose:
            logging.debug("------------")
            for region in initialRegions:
                logging.debug("Initial region {}".format(region))
            logging.debug("Time: {:.3f}s".format(time.time() - startTimePLAInit))
            logging.debug("------------")

        # Find upper bound
        found = False
        logging.info("No initial regions: {}".format(len(initialRegions)))
        while not found:
            self.checker = pla_helper.init_solver(upperBound, self.model, self.env, self.program)
            for region in initialRegions:
                result = self.check(region)
                if result != stormpy.pars.RegionResult.ALLVIOLATED and result != stormpy.pars.RegionResult.CENTERVIOLATED:
                    if self.verbose:
                        logging.debug("------------")
                        logging.debug("Found upper bound: {}".format(upperBound))
                        logging.debug("Time: {:.3f}s".format(time.time() - startTimePLAInit))
                        logging.debug("------------")
                    found = True
                    break
            if not found:
                if self.verbose:
                    logging.debug("------------")
                    logging.debug("New upper bound: {}".format(upperBound))
                    logging.debug("Time: {:.3f}s".format(time.time() - startTimePLAInit))
                    logging.debug("------------")
                lowerBound = upperBound
                upperBound *= 2

        # Find optimum by changing the threshold and only keeping satisfying regions
        satRegions = initialRegions
        unknownRegions = []
        oldSatRegions = list(initialRegions)
        oldUnknownRegions = []
        startTimePLA = time.time()
        while upperBound - lowerBound > self.config.precision and intervalSize > self.config.precision / 100:
            threshold = (lowerBound + upperBound) / 2
            satRegions, unknownRegions = self.compute_satisfying_regions(threshold, satRegions + unknownRegions, intervalSize, self.env)
            logging.info("Regions for threshold {}  after call: {} sat, {} unknown, {} calls, {}s average call time, {} splits".format(
                threshold, len(satRegions), len(unknownRegions), self.no_calls, self.time_calls / self.no_calls, self.no_splits))
            if self.verbose:
                logging.debug("------------")
                logging.debug("Threshold: [{}, {}], precision: {:.1e}".format(lowerBound, upperBound, upperBound - lowerBound))
                tmp = sort_regions(list(satRegions), [self.var])
                for region in tmp:
                    logging.debug("Sat region {}".format(region))
                tmp = sort_regions(list(unknownRegions), [self.var])
                for region in tmp:
                    logging.debug("Unknown region {}".format(region))
                logging.debug("Time: {:.3f}s".format(time.time() - startTimePLA))
                logging.debug("------------")

            if not satRegions and not unknownRegions:
                # No satisfying region -> update lower bound
                lowerBound = threshold
                # Restore old regions
                satRegions = list(oldSatRegions)
                unknownRegions = list(oldUnknownRegions)
            elif satRegions:
                # Some satisfying regions -> update upper bound
                upperBound = threshold
                # Update old regions
                oldSatRegions = list(satRegions)
                oldUnknownRegions = list(unknownRegions)
            else:
                # No satisfying regions but some unknown regions remain
                assert not satRegions and unknownRegions
                # Try again with smaller intervals
                intervalSize /= 2
                # Use remaining unknown regions as everything else is already discarded

        # Return best values
        if not satRegions:
            # Restore last known satRegions
            satRegions = list(oldSatRegions)
        logging.info("Regions after call: {} sat, {} unknown, {} calls, {}s average call time, {} splits".format(len(satRegions), len(unknownRegions), self.no_calls,
                                                                                                                 self.time_calls / self.no_calls, self.no_splits))
        return sort_regions(satRegions, [self.var]), sort_regions(unknownRegions, [self.var]), Interval(lowerBound, upperBound), time_roots
