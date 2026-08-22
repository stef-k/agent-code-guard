package sample

func DeeplyNested(values []int) int {
	if len(values) > 0 {
		for _, value := range values {
			for value > 0 {
				if value%2 == 1 {
					return value
				}
				value--
			}
		}
	}
	return 0
}

func Branching(a, b, c, d bool) int {
	result := 0
	if a { result++ }
	if b { result++ }
	if c { result++ }
	if d { result++ }
	return result
}

func Expressions(a, b, c bool) bool {
	return a && b || c
}

func Switches(value any) int {
	switch typed := value.(type) {
	case int:
		return typed
	case string:
		return len(typed)
	default:
		return 0
	}
}

func ElseIf(a, b bool) int {
	if a {
		return 1
	} else if b {
		return 2
	}
	return 0
}

func ValueSwitch(value int) string {
	switch value {
	case 1:
		return "one"
	case 2, 3:
		return "few"
	default:
		return "other"
	}
}
