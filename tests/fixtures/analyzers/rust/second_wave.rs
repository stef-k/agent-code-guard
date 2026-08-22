fn evaluate(value: Option<i32>) -> i32 {
    if let Some(current) = value {
        while let Some(next) = value {
            if next > current { break; }
        }
    }
    match value {
        Some(current) if current > 10 => current,
        Some(current) => current,
        None => 0,
    }
}

trait Work {
    fn default_run(&self) { loop { break; } }
}

impl Work for Worker {
    fn default_run(&self) { for item in 0..1 { use_item(item); } }
}

fn closures() {
    let stable = |ready: bool| if ready && true { 1 } else { 0 };
    consume(|value| value > 0);
}
