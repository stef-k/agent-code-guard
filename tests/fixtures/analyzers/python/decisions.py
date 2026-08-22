def deeply_nested(value):
    if value:
        for item in value:
            while item > 0:
                if item % 2:
                    return item
                item -= 1
    return 0


def branching(a, b, c, d):
    if a:
        a = 0
    elif b:
        b = 0
    if c:
        c = 0
    if d:
        d = 0
    return a + b + c + d


def expressions(items, left, right):
    selected = [item for item in items if item > 0]
    choice = left if left and right else right
    return selected, choice


def patterns(value):
    try:
        match value:
            case 1:
                return "one"
            case 2 | 3:
                return "few"
            case _:
                return "other"
    except ValueError:
        return "invalid"
