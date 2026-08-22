#define ENABLED 1
#ifdef ENABLED
template <class T>
T choose(T value) {
    if (value && ENABLED) {
        while (value) {
            value--;
        }
    }
    return value;
}
#endif

class Worker {
public:
    Worker() {}
    ~Worker() {}
    int operator()(int value) {
        return value ? 1 : 0;
    }
    class Nested {
    public:
        int run(int value) {
            switch (value) {
            case 1: return 1;
            default: return 0;
            }
        }
    };
};

auto stable = [](int value) {
    try {
        for (int i = 0; i < value; ++i) {}
    } catch (...) {}
    return value;
};

void consume() {
    use([](bool ready) { return ready || false; });
}

#if UNKNOWN_MACRO
int configured() { return 1; }
#endif
