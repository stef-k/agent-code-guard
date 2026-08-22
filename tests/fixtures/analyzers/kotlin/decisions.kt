package sample

fun deeplyNested(values: List<Int>): Int {
    if (values.isNotEmpty()) {
        for (value in values) {
            var current = value
            while (current > 0) {
                if (current % 2 == 1) {
                    return current
                }
                current--
            }
        }
    }
    return 0
}

fun branching(a: Boolean, b: Boolean, c: Boolean, d: Boolean): Int {
    var result = 0
    if (a) result++
    if (b) result++
    if (c) result++
    if (d) result++
    return result
}

fun expressions(a: Boolean, b: Boolean, c: Boolean, value: String?): Boolean {
    val fallback = value ?: "none"
    val length = value?.length
    val ignoredLambda = { item: Int -> if (item > 0) item else 0 }
    ignoredLambda(length ?: 0)
    return a && b || c || fallback.length == length
}

fun choices(value: Int): String = when (value) {
    1 -> "one"
    2, 3 -> "few"
    else -> "other"
}

fun localOwner(value: Int): Int {
    fun local(item: Int): Int = item * 2
    return local(value)
}

fun elseIf(a: Boolean, b: Boolean): Int {
    return if (a) {
        1
    } else if (b) {
        2
    } else {
        0
    }
}

fun exceptions(value: String): Int {
    return try {
        if (value.isEmpty()) 0 else value.toInt()
    } catch (error: NumberFormatException) {
        -1
    } catch (error: IllegalArgumentException) {
        -2
    }
}
