<template>
  <main>{{ result }}</main>
</template>

<script setup lang="ts">
type Input = { active?: boolean; value: number };

const calculate = (input: Input): number => {
    if (input?.active) {
        return input.value;
    }
    return 0;
};
</script>

<script lang="ts">
export function normalize(value: number): number {
    return value > 0 ? value : 0;
}
</script>

<style scoped>
main { color: blue; }
</style>
