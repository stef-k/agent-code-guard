func evaluate(_ value: Int?) -> Int {
    guard let value = value else { return 0 }
    if value > 0 && value < 10 {
        for item in 0..<value { print(item) }
    } else if value < 0 {
        return -1
    }
    switch value {
    case 1: return 1
    case let item where item > 2: return item
    default: return 0
    }
}

class Worker {
    init() {}
    func run() {
        while true { break }
        do { throw Failure.example } catch { return }
    }
}

extension Worker {
    func extra() {}
}

protocol Work {
    func required()
    func provided() { repeat {} while false }
}

let stable = { (value: Int) -> Int in
    return value > 0 ? value : 0
}

func callbacks() {
    consume { value in value && true }
}
