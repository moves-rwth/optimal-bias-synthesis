import argparse
import logging
import math
import os
import time
from enum import Enum

from matplotlib import pyplot

from finetuning import pla_single
from finetuning import pla_parallel
from finetuning import pla_old
import finetuning.analyse as analyse
import finetuning.build as build
import finetuning.sample as sample
from finetuning.parser import get_ratfunc
from finetuning.result import Result
from finetuning.config import Config


class TaskType(Enum):
    approx = 'approx'
    rat_func = 'rat_func'
    sample = 'sample'

    def __str__(self):
        return self.value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyse parametric self-stabilizing algorithms.')

    parser.add_argument('--task', type=TaskType, choices=list(TaskType), required=True)
    parser.add_argument('--file', help='the prism file to analyse', required=True)

    # For approximation
    parser.add_argument('--approx', help='approximate the optimum up to the given precision', type=float, default=0)
    parser.add_argument('--parallel', '-p', help='enable parallelization of PLA with given number of processes', type=int, default=1)
    parser.add_argument('--hybrid', help='build symbolic model first', action="store_true")
    parser.add_argument('--old', help="use old implementation of PLA", action="store_true")

    # For sampling
    parser.add_argument('--no-samples', help='number of samples per parameter', type=int, default=3)
    parser.add_argument('--csv', help='output csv file', default=None)

    parser.add_argument('--exact', help="use exact numbers instead of floats", action="store_true")
    parser.add_argument('--memory', help='memory limit', type=int, default=4096)

    parser.add_argument('--verbose', '-v', help='print more output', action="store_true")
    args = parser.parse_args()

    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG if args.verbose else logging.INFO)

    task_type = args.task

    epsilon = 1e-10

    config = Config(args.hybrid, args.parallel, args.approx, args.memory, args.no_samples, args.exact)

    if task_type is TaskType.approx:
        if args.approx <= 0:
            logging.error("Approximation error must be greater than zero.")
            exit(1)

        # Compute optima via PLA
        logging.info("Running PLA for '{}' with {}".format(args.file, config))

        if args.old:
            if args.exact:
                config.exact = False
                logging.warning("Exact number not supported with old implementation.")
            if config.processes > 1:
                logging.warning("Multiple processes are not supported with old implementation.")
            # Sequential PLA with old implementation (for reference results)
            result = Result(args.file, config)
            # Building model
            start_time = time.time()
            model, program, _, time_build, time_bisim = build.build_model(args.file, config.hybrid, sylvan_threads=1, sylvan_memory=config.memory_limit)
            result.time_build = time_build
            result.time_bisimulation = time_bisim
            # Get variable
            variables = build.get_parameters(model)
            # PLA
            start_pla = time.time()
            old_pla = pla_old.PLAOld(model, program, config, verbose=args.verbose)
            optima, unknownRegions, region_ert, time_roots = old_pla.compute_optima_via_pla()
            end_pla = time.time()
            # Set result
            result.time_roots = time_roots
            result.time_analysis = end_pla - start_pla
            result.time_total = end_pla - start_time
            result.result_ert = region_ert
            result.result_region = optima
        else:
            # Use new (optimized) PLA computation
            if config.processes > 1:
                # Parallel PLA
                parallel_pla = pla_parallel.PLAParallel(config)
                result = parallel_pla.find_optimum(args.file, verbose=args.verbose)
            else:
                # Sequential PLA
                # Building model
                start_time = time.time()
                model, program, _, time_build, time_bisim = build.build_model(args.file, config.hybrid, sylvan_threads=1, sylvan_memory=config.memory_limit)
                # Get variable
                variables = build.get_parameters(model)
                # PLA
                single_pla = pla_single.PLASingle(model, config)
                result = single_pla.find_optimum(args.file, verbose=args.verbose)
                # Set result
                result.time_build = time_build
                result.time_bisimulation = time_bisim
                result.time_total = time.time() - start_time

        logging.info(result)

    elif task_type is TaskType.sample:
        logging.info("Sampling points.")
        # Building model
        model, _, formula, time_build, time_bisim = build.build_model(args.file, config.hybrid, sylvan_threads=config.processes, sylvan_memory=config.memory_limit)
        parameters = build.get_parameters(model)

        # Sampling
        start_sampling = time.time()
        sample_points = sample.generate_sample_points(parameters, config.no_samples, near_bounds=True, eps=config.eps)
        samples = sample.sample(model, formula, parameters, sample_points, config.exact)
        time_sampling = time.time() - start_sampling
        logging.info("Sampled {} points in {}s".format(len(sample_points), time_sampling))
        sample_string = "\n".join(["{}: {}".format(point, sample) for point, sample in samples])
        logging.info("Sample results:\n{}".format(sample_string))
        if args.csv:
            sample.export_csv(args.csv, samples, parameters, max_value=1000)
            logging.info("Exported to {}".format(args.csv))

    elif task_type is TaskType.rat_func:
        # Compute optima via rational function
        startTimeMC = time.time()
        if args.ratfunc:
            logging.debug("Analysing %s" % args.ratfunc)
            ratFunc = get_ratfunc(args.ratfunc)
        else:
            assert args.file
            logging.debug("Analysing %s" % args.file)
            ratFunc = analyse.compute_rational_function(args.file)
        endTimeMC = time.time()
        logging.debug("Rational function: %s" % ratFunc)
        vars = list(ratFunc.gather_variables())
        assert len(vars) == 1
        var = vars[0]

        if args.verbose:
            # Evaluation
            evaluations = [{var: 0 + epsilon}, {var: 0.1}, {var: 0.2}, {var: 0.3}, {var: 0.4}, {var: 0.47}, {var: 0.5},
                           {var: 0.53}, {var: 0.6}, {var: 0.64}, {var: 0.69}, {var: 0.7}, {var: 0.8}, {var: 0.9},
                           {var: 1 - epsilon}]
            results = analyse.evaluate_rational_function(ratFunc, evaluations)
            logging.info("Evaluation:")
            assert len(evaluations) == len(results)
            for i in range(0, len(evaluations)):
                str = ", ".join([("{}={:.2f}".format(var, val)) for (var, val) in evaluations[i].items()])
                logging.info("\t{}: {:.5f}".format(str, float(results[i])))

        if args.plot_file or args.show_plot:
            # Plot
            evaluations = []
            xPts = []
            yPts = []
            val = 0.05
            while val < 1:
                evaluations.append({var: val})
                xPts.append(val)
                val += 0.05
            results = analyse.evaluate_rational_function(ratFunc, evaluations)
            assert len(evaluations) == len(results)
            maxVal = 0
            for i in range(0, len(evaluations)):
                val = float(results[i])
                yPts.append(val)
                maxVal = max(maxVal, val)
            pyplot.plot(xPts, yPts, 'b-')
            pyplot.axis([0, 1, 0, math.ceil(maxVal)])
            if args.show_plot:
                pyplot.show()
            if args.plot_file:
                pyplot.savefig(args.plot_file)
                logging.info("Saved plot to {}".format(args.plot_file))

        # Derivation
        startTimeOpt = time.time()
        optima = analyse.compute_optimum(ratFunc, vars[0])
        filename = args.file if args.file else args.ratfunc
        if len(optima) > 0:
            for optimum in optima:
                floatOpt = optimum.as_decimal(10)
                floatOpt = float(floatOpt.replace("?", ""))
                logging.debug("Optimum: {} ({:.5f})".format(optimum, floatOpt))
                valOpt = analyse.evaluate_rational_function(ratFunc, [{var: floatOpt}])[0]
                logging.info("Optimal value on {} for {} = {:.5f}: {:.5f}".format(os.path.basename(filename), var, floatOpt, float(valOpt)))
        else:
            logging.debug("No optimum found.")
            results = analyse.evaluate_rational_function(ratFunc, [{var: 0 + epsilon}, {var: 1 - epsilon}])
            floatOpt = 0.001 if results[0] < results[1] else 1
            valOpt = analyse.evaluate_rational_function(ratFunc, [{var: floatOpt}])[0]
            logging.info("Best value on {} for {} = {:.5f}: {:.5f}".format(os.path.basename(filename), var, floatOpt, float(valOpt)))
        endTimeOpt = time.time()

        # Times
        timeMC = endTimeMC - startTimeMC
        timeOpt = endTimeOpt - startTimeOpt
        timeTotal = endTimeOpt - startTimeMC
        logging.info("Times: {:.3f}s for model checking, {:.3f}s for computing optimum, {:.3f}s in total".format(timeMC, timeOpt, timeTotal))

    else:
        logging.error("Task {} not valid.".format(task_type))
        exit(1)
