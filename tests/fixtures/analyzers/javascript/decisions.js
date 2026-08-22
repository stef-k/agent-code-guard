export function deeplyNested(values) {
    if (values.length > 0) {
        for (const value of values) {
            let current = value;
            while (current > 0) {
                if (current % 2 === 1) {
                    return current;
                }
                current--;
            }
        }
    }
    return 0;
}

export function branching(a, b, c, d) {
    let result = 0;
    if (a) result++;
    if (b) result++;
    if (c) result++;
    if (d) result++;
    return result;
}

export function elseIf(a, b) {
    if (a) return 1;
    else if (b) return 2;
    return 0;
}

export function expressions(a, b, c, value) {
    const length = value?.name?.length ?? 0;
    return a && b || c ? length > 0 : false;
}

export function choices(value) {
    switch (value) {
        case 1: return "one";
        case 2:
        case 3: return "few";
        default: return "other";
    }
}

export function callbackOwner(items, promise) {
    const mapped = items.map(item => {
        if (item.active) return item.value;
        return 0;
    });
    promise.then(result => result && consume(result));
    return mapped;
}

export function exceptions(value) {
    try {
        if (value.length === 0) return 0;
        return JSON.parse(value);
    } catch (error) {
        return -1;
    }
}
