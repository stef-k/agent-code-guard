namespace Sample;

public static class Callables
{
    public static int Simple(int value) => value + 1;

    public static int LongLinear(int value)
    {
        var first = value + 1;
        var second = first + 1;
        var third = second + 1;
        var fourth = third + 1;
        var fifth = fourth + 1;
        var sixth = fifth + 1;
        return sixth;
    }

    [Audit]
    public static int Documented(
        int left,
        int right)
    {
        // Comment lines and blanks are physical source lines.

        return left + right;
    }

    public static int LocalOwner(int value)
    {
        int Local(int item) => item * 2;
        return Local(value);
    }
}

public sealed class Worker
{
    public Worker(int value) => Value = value;
    public int Value { get; }
}
