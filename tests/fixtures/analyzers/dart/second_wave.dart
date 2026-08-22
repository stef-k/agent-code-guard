Future<int> evaluate(int? value) async {
  int local() { return 1; }
  var stable = (int item) => item > 0 ? item : 0;
  consume((item) => item && true);
  if (value != null && value > 0) {
    for (var i = 0; i < value; i++) {
      while (i > 1) { break; }
    }
  }
  switch (value) {
    case 1: return 1;
    default: return value?.abs() ?? 0;
  }
}

class Worker {
  Worker() {}
  int run() {
    try { return 1; } catch (error) { return 0; }
  }
}
