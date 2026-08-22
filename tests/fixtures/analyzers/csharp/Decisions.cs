namespace Sample;

public static class Decisions
{
    public static int DeeplyNested(int[] values)
    {
        if (values.Length > 0)
        {
            foreach (var value in values)
            {
                var current = value;
                while (current > 0)
                {
                    if (current % 2 == 1)
                    {
                        return current;
                    }
                    current--;
                }
            }
        }
        return 0;
    }

    public static int Branching(bool a, bool b, bool c, bool d)
    {
        var result = 0;
        if (a) result++;
        if (b) result++;
        if (c) result++;
        if (d) result++;
        return result;
    }

    public static bool Expressions(bool a, bool b, bool c, int value) =>
        a && b || c ? value > 0 : value < 0;

    public static string Choices(int value) => value switch
    {
        1 => "one",
        2 or 3 => "few",
        _ => "other"
    };
}
