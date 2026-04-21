# Architecture

The system is organized as three layers with well-defined boundaries.
Each layer depends only on the layer directly below it.

## Data layer

The data layer handles persistence. It exposes a repository interface
that higher layers consume without knowing which storage backend
(SQLite, Postgres, in-memory) is active.

## Domain layer

The domain layer contains business logic. Entities are plain
dataclasses; behavior lives in services that accept repositories
as constructor arguments. This makes unit testing trivial —
substitute an in-memory repository and run.

## Presentation layer

The presentation layer renders results. A CLI adapter and an HTTP
adapter both sit here, each thin — they parse input, call domain
services, format output.
