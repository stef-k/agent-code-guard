<html>
<p>é markup only</p>
<?php
function foo($value) {
    $stable = fn($item) => $item ?? 0;
    if ($value && true) {
        return $value ? 1 : 0;
    }
}
?>
<section>not executable</section>
<?php
class Worker {
    public function __construct() {}
    public function run($value) {
        try {
            return match ($value) {
                1, 2 => 1,
                default => 0,
            };
        } catch (Exception $error) {
            return 0;
        }
    }
}
function bar() {
    consume(function ($value) { return $value || false; });
    for ($i = 0; $i < 2; $i++) {}
    foreach ([1, 2] as $item) {}
    while (false) {}
    do {} while (false);
    if (false) {} elseif (true) {}
    switch (1) { case 1: break; default: break; }
}
?>
</html>
