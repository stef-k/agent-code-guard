def simple(value):
    return value + 1


def long_linear(value):
    first = value + 1
    second = first + 1
    third = second + 1
    fourth = third + 1
    fifth = fourth + 1
    sixth = fifth + 1
    return sixth


@audit
def documented(
    left,
    right,
):
    # Comment lines and blanks are physical source lines.

    return left + right


def outer(value):
    def local(item):
        return item * 2
    return local(value)


class Worker:
    def method(self, value):
        return value
