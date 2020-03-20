import os
import re
import logging

from finetuning.region import Point, Interval, Region
from finetuning.config import Config


class Result:
    """
    Analysis result.
    """

    def __init__(self, file, config):
        self.file = os.path.basename(file)
        self.config = config
        self.no_states = 0
        self.no_transitions = 0
        self.time_build = 0
        self.time_bisimulation = 0
        self.time_export = 0
        self.time_load = 0
        self.time_roots = 0
        self.time_analysis = 0
        self.time_total = 0
        self.result_ert = None
        self.best_sample = None
        self.result_region = []
        self.error = None

    def __str__(self):
        s = "===== SUMMARY =====\n"
        s += "Result for '{}' with {}\n".format(self.file, self.config)
        s += "Times:\n"
        s += "\tBuilding:       {:.3f}s\n".format(self.time_build)
        s += "\tBisimulation:   {:.3f}s\n".format(self.time_bisimulation)
        s += "\tExport:         {:.3f}s\n".format(self.time_export)
        s += "\tLoad:           {:.3f}s\n".format(self.time_load)
        s += "\tRoots:          {:.3f}s\n".format(self.time_roots)
        s += "\tAnalysis:       {:.3f}s\n".format(self.time_analysis)
        s += "\tTotal:          {:.3f}s\n".format(self.time_total)
        s += "Result:\n"
        s += "\tOptimum: {}\n".format(self.result_ert)
        s += "\tBest sample: {}\n".format(self.best_sample)
        s += "\tRegions:\n"
        s += "\n".join("\t\t{}".format(region) for region in self.result_region)
        return s

    @staticmethod
    def parse_result(file):
        parse_state = 0
        result = None
        old_algorithm = False
        with open(file, 'r') as f:
            for line in f:
                if result is not None and result.error is None:
                    # Check for timeout
                    match = re.search(r"JOB .* ON .* CANCELLED AT .* DUE TO TIME LIMIT", line)
                    if match:
                        result.error = "TO"
                    # Check for memout
                    match = re.search(r"MemoryError: std::bad_alloc", line)
                    if match:
                        result.error = "MO"
                    match = re.search(r"BDD Unique table full", line)
                    if match:
                        result.error = "MO"
                    # Check cancellation
                    match = re.search(r"\*\*\* JOB .* ON .* CANCELLED AT .* DUE TO (.*) \*\*\*", line)
                    if match:
                        cancel_reason = match.group(1)
                        if cancel_reason == "TIME LIMIT":
                            result.error = "TO"
                        else:
                            result.error = "Cancelled ({})".format(match.group(1))
                    # Check exitcode
                    match = re.search(r"exitcode: (.*)", line)
                    if match:
                        exitcode = int(match.group(1))
                        if exitcode > 0:
                            result.error = "Exitcode {}".format(exitcode)

                if parse_state == 0:
                    match = re.search(r"Executing.*--old", line)
                    if match:
                        old_algorithm = True
                        continue
                    match = re.search(r".*Running PLA for '(.*)' with (.*)", line)
                    if match:
                        file_name = match.group(1)
                        config_str = match.group(2)
                        config = Config.parse_string(config_str)
                        assert config is not None
                        if old_algorithm:
                            config.old_algorithm = True
                        result = Result(file_name, config)
                        parse_state += 1
                elif parse_state == 1:
                    match = re.search(r"Building model took (.*)s", line)
                    if match:
                        result.time_build = float(match.group(1))
                        parse_state += 1
                elif parse_state == 2:
                    match = re.search(r".*Model after bisimulation: (.*) states and (.*) transitions.", line)
                    if match:
                        result.no_states = int(match.group(1))
                        result.no_transitions = int(match.group(2))
                        parse_state += 1
                elif parse_state == 3:
                    match = re.search(r"Computing bisimulation quotient took (.*)s", line)
                    if match:
                        result.time_bisimulation = float(match.group(1))
                        parse_state += 1
                        if result.config.processes == 1:
                            # Skip the next steps as there will be no corresponding output
                            parse_state = 6
                elif parse_state == 4:
                    match = re.search(r"Exporting model took (.*)s", line)
                    if match:
                        result.time_export = float(match.group(1))
                        parse_state += 1
                elif parse_state == 5:
                    match = re.search(r"Loading model took (.*)s", line)
                    if match:
                        result.time_load = float(match.group(1))
                        parse_state += 1
                elif parse_state == 6:
                    match = re.search(r"Computing roots took (.*)s", line)
                    if match:
                        result.time_roots = float(match.group(1))
                        parse_state += 1
                elif parse_state == 7:
                    # Match best samples as long as no summary was given
                    match = re.search(r", best sample: (\(.*\)), ", line)
                    if match:
                        result.best_sample = Point.parse(match.group(1))
                    else:
                        match = re.search(r"===== SUMMARY =====", line)
                        if match:
                            parse_state += 1
                elif parse_state == 8:
                    match = re.search(r"\tAnalysis:\s*(.*)s", line)
                    if match:
                        result.time_analysis = float(match.group(1))
                        parse_state += 1
                elif parse_state == 9:
                    match = re.search(r"\tTotal:\s*(.*)s", line)
                    assert match
                    result.time_total = float(match.group(1))
                    parse_state += 1
                elif parse_state == 10:
                    match = re.search(r"Result:", line)
                    assert match
                    parse_state += 1
                elif parse_state == 11:
                    match = re.search(r"\tOptimum: (.*)", line)
                    assert match
                    result.result_ert = Interval.parse(match.group(1))
                    parse_state += 1
                elif parse_state == 12:
                    # Best sample might be present or not
                    match = re.search(r"\tBest sample: (.*)", line)
                    if match:
                        if match.group(1) == "None":
                            if not result.config.old_algorithm:
                                logging.warning("No best sample on {}".format(file))
                        else:
                            result.best_sample = Point.parse(match.group(1))
                    else:
                        match = re.search(r"\tRegions:", line)
                        assert match
                        parse_state += 1
                elif parse_state == 13:
                    match = re.search(r"\t\t(.*)", line)
                    if match:
                        result.result_region.append(Region.parse(match.group(1)))
                    else:
                        break
        if parse_state != 13 and not result.error:
            logging.warning("Ended in parsing state {} on {}".format(parse_state, file))
        return result
