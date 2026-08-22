package sample

fun simple(value: Int): Int = value + 1

fun longLinear(value: Int): Int {
    val first = value + 1
    val second = first + 1
    val third = second + 1
    val fourth = third + 1
    val fifth = fourth + 1
    val sixth = fifth + 1
    return sixth
}

@Audit
fun documented(
    left: Int,
    right: Int,
): Int {
    // Comment lines and blanks are physical source lines.

    return left + right
}

class Worker {
    fun method(value: Int): Int = value

    constructor(value: Int) {
        require(value >= 0)
    }
}
