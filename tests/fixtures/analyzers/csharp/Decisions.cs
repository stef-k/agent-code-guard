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

    public static int ElseIf(bool a, bool b)
    {
        if (a) return 1;
        else if (b) return 2;
        return 0;
    }

    public static string ClassicSwitch(int value)
    {
        switch (value)
        {
            case 1: return "one";
            case 2:
            case 3: return "few";
            default: return "other";
        }
    }

    public static int Exceptions(string value)
    {
        try
        {
            if (value.Length == 0) return 0;
            return int.Parse(value);
        }
        catch (FormatException) { return -1; }
        catch (OverflowException) { return -2; }
    }

    public static int WildcardSwitch(object value)
    {
        switch (value)
        {
            case int number: return number;
            case var _: return 0;
        }
    }
}
