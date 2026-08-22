package sample

func Simple(value int) int {
	return value + 1
}

func LongLinear(value int) int {
	first := value + 1
	second := first + 1
	third := second + 1
	fourth := third + 1
	fifth := fourth + 1
	sixth := fifth + 1
	return sixth
}

func Documented(
	left int,
	right int,
) int {
	// Comment lines and blanks are physical source lines.

	return left + right
}

type Worker struct{}

func (worker Worker) Method(value int) int {
	return value
}
