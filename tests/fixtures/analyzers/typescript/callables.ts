export interface Service {
    calculate<T>(value: T, optional?: boolean): T;
}

export type Handler = (value: string) => number;

export function generic<T>(
    value: T,
    optional?: boolean,
): T {
    return optional ? value : value;
}

export const arrow: Handler = (value: string): number => {
    return value.length;
};

export const expression = function <T>(value: T): T {
    return value;
};

export class Worker {
    constructor(public readonly value: number) {}

    @Audit()
    method<T>(value: T, optional?: boolean): T {
        return optional ? value : value;
    }
}
