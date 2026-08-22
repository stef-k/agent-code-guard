export function typedDecisions<T extends { active?: boolean }>(
    item: T | undefined,
    fallback: T,
): T {
    if (item?.active && fallback.active) return item;
    return item ?? fallback;
}

export function callbackOwner(values: number[], promise: Promise<number>): number[] {
    const mapped = values.map((value: number) => {
        if (value > 0) return value;
        return 0;
    });
    promise.then((result: number) => result > 0 ? result : 0);
    return mapped;
}
