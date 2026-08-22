export function simple(value) {
    return value + 1;
}

export function longLinear(value) {
    const first = value + 1;
    const second = first + 1;
    const third = second + 1;
    const fourth = third + 1;
    const fifth = fourth + 1;
    const sixth = fifth + 1;
    return sixth;
}

export const arrow =
    (left, right) => {
        // Comment lines and blanks are physical source lines.

        return left + right;
    };

export const expression = function (value) {
    return value * 2;
};

export const helpers = {
    method(value) {
        return value;
    },
};

export class Worker {
    constructor(value) {
        this.value = value;
    }

    method(value) {
        return value;
    }
}

export function localOwner(value) {
    const local = (item) => item * 2;
    const localExpression = function (item) {
        return item + 1;
    };
    return local(localExpression(value));
}

export var
    legacy = function (value) {
        return value;
    };
