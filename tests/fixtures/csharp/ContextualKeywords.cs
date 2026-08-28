internal static class Repro
{
    private static int Configure(bool async) => async ? 1 : 0;

    public static int Sync() => Configure(async: false);

    public static int Async() => Configure(async: true);
}
