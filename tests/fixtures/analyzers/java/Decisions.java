package sample;

public final class Decisions {
    public static int deeplyNested(int[] values) {
        if (values.length > 0) {
            for (int value : values) {
                int current = value;
                while (current > 0) {
                    if (current % 2 == 1) {
                        return current;
                    }
                    current--;
                }
            }
        }
        return 0;
    }

    public static int branching(boolean a, boolean b, boolean c, boolean d) {
        int result = 0;
        if (a) result++;
        if (b) result++;
        if (c) result++;
        if (d) result++;
        return result;
    }

    public static int elseIf(boolean a, boolean b) {
        if (a) return 1;
        else if (b) return 2;
        return 0;
    }

    public static boolean expressions(boolean a, boolean b, boolean c, int value) {
        return a && b || c ? value > 0 : value < 0;
    }

    public static int exceptions(String value) {
        try {
            if (value.isEmpty()) return 0;
            return Integer.parseInt(value);
        } catch (NumberFormatException error) {
            return -1;
        } catch (IllegalArgumentException error) {
            return -2;
        }
    }

    public static String statementSwitch(int value) {
        switch (value) {
            case 1: return "one";
            case 2:
            case 3: return "few";
            default: return "other";
        }
    }

    public static String expressionSwitch(int value) {
        return switch (value) {
            case 1 -> "one";
            case 2, 3 -> "few";
            default -> "other";
        };
    }
}
