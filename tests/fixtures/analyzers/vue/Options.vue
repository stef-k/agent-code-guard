<template>
  <div>
    <section>{{ value }}</section>
  </div>
</template>

<script>
export function calculate(value) {
    if (value > 0) {
        return value;
    }
    return 0;
}
</script>

<style>
.example { color: red; }
</style>
