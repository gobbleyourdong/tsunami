# Tool latency bench

## Phase A — direct tool.execute() only

| tool | shape | direct ms | error |
|---|---|---:|---|
| `file_read` | small | 0.1 |  |
| `file_read` | medium | 0.5 |  |
| `file_write` | small | 0.3 |  |
| `file_write` | medium | 0.2 |  |
| `file_edit` | single | 0.3 |  |
| `shell_exec` | echo | 1.7 |  |
| `shell_exec` | ls | 1.8 |  |
| `message_chat` | short | 0.0 | REFUSED: cannot end the task before doing any work. Your bia |
| `message_result` | short | 0.0 |  |
| `undertow` | small | 3720.6 | QA: FAIL
  ✗ 3 dependency unused: @types/matter-js, marked,  |
| `plan_update` | trivial | 0.0 | No agent state available |
| `plan_advance` | trivial | 0.0 | No active plan |
