import re
import stormpy


class Config:
    """
    Configuration.
    """

    def __init__(self, hybrid, processes, precision, memory_limit, no_samples=3, exact=False, old_algorithm=False):
        self.hybrid = hybrid
        self.processes = processes
        self.precision = precision
        self.memory_limit = memory_limit
        self.no_samples = no_samples
        self.exact = exact
        self.old_algorithm = old_algorithm
        self.eps = 1e-10
        self.linear_equation_solver = None  # Use default (i.e. stormpy.EquationSolverType.topological)

    def hybrid_str(self):
        return "symbolic" if self.hybrid else "sparse"

    def config_string(self):
        return "{}-{}-{}{}".format(self.processes, self.precision, self.hybrid_str(), "-old" if self.old_algorithm else "")

    @staticmethod
    def parse_string(string):
        old_algorithm = False
        match = re.search(r"Config: (.*) building, (.*) processes, precision (.*), memory limit (.*) MB(.*)", string)
        if match:
            if match.group(1) == "symbolic":
                hybrid = True
            else:
                assert match.group(1) == "sparse"
                hybrid = False
            processes = int(match.group(2))
            precision = float(match.group(3))
            memory_limit = int(match.group(4))
            if match.group(5) != "":
                assert match.group(5) == " old algorithm"
                old_algorithm = True
            return Config(hybrid, processes, precision, memory_limit, old_algorithm=old_algorithm)
        return None

    def __str__(self):
        return "Config: {} building, {} processes, precision {}, memory limit {} MB{}".format(self.hybrid_str(), self.processes, self.precision, self.memory_limit,
                                                                                              " old algorithm" if self.old_algorithm else "")
