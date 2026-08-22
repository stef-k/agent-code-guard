package sample;

public final class Callables {
    public static int simple(int value) {
        return value + 1;
    }

    public static int longLinear(int value) {
        int first = value + 1;
        int second = first + 1;
        int third = second + 1;
        int fourth = third + 1;
        int fifth = fourth + 1;
        int sixth = fifth + 1;
        return sixth;
    }

    @Audit
    public Callables(
        int left,
        int right
    ) {
        // Comment lines and blanks are physical source lines.

        this.value = left + right;
    }

    private final int value;
}
