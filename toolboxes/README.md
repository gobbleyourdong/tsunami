# Toolboxes

Additional tool groups that the agent can load on demand via `load_toolbox`.
Only load what the current task requires — every tool costs context.

| Toolbox | Tools | What it does |
|---------|-------|-------------|
| browser | 13 | Navigate, click, fill forms, screenshot pages, extract content |
| webdev | 4 | Scaffold React+Tailwind projects, serve, screenshot, generate assets |
| generate | 1 | Create images via the diffusion server |
| services | 3 | Expose local services via tunnel, schedule cron jobs, view binary files |
| parallel | 1 | Run 5+ independent tasks concurrently via map |
