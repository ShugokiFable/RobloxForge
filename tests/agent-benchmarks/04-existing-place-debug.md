# Existing-place debug benchmark

Seed a disposable place with one intentional nil-reference bug and unrelated scripts.

Prompt:
> Fix the runtime bug without rewriting unrelated systems.

Pass:
- explores existing hierarchy/source first,
- reproduces,
- reads exact error,
- targeted fix,
- retests same scenario,
- does not replace whole project.
