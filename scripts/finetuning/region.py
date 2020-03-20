import re

import stormpy


class Point:
    """
    Single point.
    """

    def __init__(self, valuation):
        self.val = valuation

    def carl_valuation(self, variables):
        assert len(variables) == len(self.val)
        valuation = dict()
        for var in variables:
            valuation[var] = stormpy.RationalRF(self.val[var.name])
        return valuation

    def get_value(self, variable):
        assert variable.name in self.val
        return self.val[variable.name]

    @staticmethod
    def parse(s):
        match = re.search(r"\((.*)\)", s)
        if match:
            valuation = dict()
            for l in match.group(1).split(", "):
                match = re.search(r"(.*): (.*)", l)
                if match:
                    var = match.group(1)
                    value = match.group(2)
                    valuation[var] = value
                else:
                    raise ValueError("Cannot parse valuation substring '{}'".format(l))
            if valuation:
                return Point(valuation)
        raise ValueError("Cannot parse point string '{}'".format(s))

    def __str__(self):
        return "({})".format(", ".join("{}: {}".format(var, value) for var, value in self.val.items()))


class Interval:
    """
    Interval for one parameter
    """

    def __init__(self, lower, upper):
        self.lower = lower
        self.upper = upper

    def middle(self):
        return (self.lower + self.upper) / 2.0

    @staticmethod
    def parse(s):
        match = re.search(r"\[(.*), (.*)\]", s)
        if match:
            lower = float(match.group(1))
            upper = float(match.group(2))
            return Interval(lower, upper)
        else:
            match = re.search(r"\((.*), (.*)\)", s)
            if match:
                lower = float(match.group(1))
                upper = float(match.group(2))
                return Interval(lower, upper)
            else:
                raise ValueError("Cannot parse interval string '{}'".format(s))

    def __eq__(self, other):
        return self.lower == other.lower and self.upper == other.upper

    def __hash__(self):
        return hash((self.lower, self.upper))

    def __str__(self):
        if isinstance(self.lower, stormpy.Rational):
            return "[{}, {}]".format(self.lower, self.upper)
        else:
            return "[{:.8f}, {:.8f}]".format(self.lower, self.upper)


class Region:
    """
    Parameter region.
    """

    def __init__(self, intervals):
        self.intervals = dict()
        for var, interval in intervals.items():
            self.intervals[var] = Interval(interval.lower, interval.upper)

    def middle(self):
        return Point({var: interval.middle() for var, interval in self.intervals.items()})

    def split_single(self, variable):
        lower = dict()
        upper = dict()
        assert variable.name in self.intervals
        for var, interval in self.intervals.items():
            if var == variable.name:
                middle = interval.middle()
                lower[var] = Interval(interval.lower, middle)
                upper[var] = Interval(middle, interval.upper)
            else:
                lower[var] = interval
                upper[var] = interval
        return [Region(lower), Region(upper)]

    def split(self, variables):
        regions = [Region(self.intervals)]
        for var in variables:
            new_regions = []
            for region in regions:
                new_regions.extend(region.split_single(var))
            regions = new_regions
        return regions

    def storm_region(self, variables):
        assert len(variables) == len(self.intervals)
        region = dict()
        for var in variables:
            interval = self.intervals[var.name]
            region[var] = (stormpy.RationalRF(interval.lower), stormpy.RationalRF(interval.upper))
        return stormpy.pars.ParameterRegion(region)

    @staticmethod
    def parse(s):
        if ":" not in s:
            # Parse as interval
            return Interval.parse(s)

        match = re.search(r"\[(.*)\]", s)
        if match:
            intervals = dict()
            found = False
            for l in match.group(1).split(" x "):
                match = re.search(r"(.*): (.*)", l)
                if match:
                    var = match.group(1)
                    interval = match.group(2)
                    intervals[var] = Interval.parse(interval)
                    found = True
                else:
                    raise ValueError("Cannot parse region substring '{}'".format(l))
            if found:
                return Region(intervals)
        raise ValueError("Cannot parse region string '{}'".format(s))

    @staticmethod
    def from_single_var(var, lower, upper):
        intervals = dict()
        intervals[var] = Interval(lower, upper)
        return Region(intervals)

    def __eq__(self, other):
        for var, interval in self.intervals.items():
            if var not in other.intervals:
                return False
            if other.intervals[var] != interval:
                return False
        return True

    def __hash__(self):
        return hash(str(self))

    def __str__(self):
        return "[{}]".format(" x ".join("{}: {}".format(var, interval) for var, interval in self.intervals.items()))


def sort_intervals(intervals):
    # Try to merge intervals
    intervals.sort(key=lambda i: i.lower)
    result = []
    upper_value = -1
    for interval in intervals:
        if interval.lower == upper_value:
            # Merge regions as they share a 'border'
            result[-1] = Interval(result[-1].lower, interval.upper)
        else:
            result.append(interval)
        upper_value = interval.upper
    return result


def sort_regions(regions, parameters):
    old_regions = regions
    # Iterate over parameter to currently try to merge
    for parameter in parameters:
        # Construct dictionary from regions without current parameter
        new_regions = dict()
        for region in old_regions:
            r_cp = Region(region.intervals)
            value = region.intervals[parameter.name]
            del r_cp.intervals[parameter.name]
            if r_cp not in new_regions:
                new_regions[r_cp] = []
            new_regions[r_cp].append(value)

        old_regions = []
        for key, intervals in new_regions.items():
            # Create merged regions
            for r in sort_intervals(intervals):
                new_region = Region(key.intervals)
                new_region.intervals[parameter.name] = r
                old_regions.append(new_region)
    return old_regions
