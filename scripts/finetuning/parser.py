import pycarl

if pycarl.has_parser():
    import pycarl.parse
    import pycarl.cln
    import pycarl.cln.parse
    import re


    def get_ratfunc(file):
        """
        Parse rational function from given result file.
        :param file: Result file.
        :return: Rational function.
        """
        result = None
        for line in open(file, 'r').readlines():
            match = re.search(r"Result (.*): (.*)", line)
            if match:
                result = match.group(2)
                break
        if not result:
            print("No rational function found")
            return None

        pair = result.split('/')
        num = pycarl.parse.deserialize(pair[0], pycarl.cln)
        ratfunc = num
        if (len(pair) > 1):
            denom = pycarl.parse.deserialize(pair[1], pycarl.cln)
            ratfunc = ratfunc / denom
        return ratfunc
else:

    def get_ratfunc(file):
        """
        Parse rational function from given result file.
        :param file: Result file.
        :return: Rational function.
        """
        raise RuntimeError("Pycarl is built without parser suppert.")
