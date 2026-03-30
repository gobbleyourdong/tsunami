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
# Deep Research Skill

Systematic multi-source research with verification and citation.

## Instructions

When activated for a research task:

1. **Discovery phase**: Run 3 search queries with different angles on the topic
2. **Extraction phase**: Visit the top 3-5 sources via browser, save key findings to workspace/notes/
3. **Verification phase**: Cross-reference claims across sources. Flag contradictions.
4. **Synthesis phase**: Write the final report in workspace/deliverables/ with proper citations

## Quality Standards

- Every factual claim must have a source URL
- Minimum 3 independent sources per conclusion
- Note publication dates — prefer recent sources
- If sources disagree, present both views with evidence strength assessment

## Output Format

Markdown report with:
- Executive summary (answers the question in 1 paragraph)
- Evidence sections with inline citations [1], [2], etc.
- Conclusion
- References section with numbered URLs

# Skill Creator

Guide for creating new skills for the Tsunami agent.

## Creating a Skill

1. Create a directory under `skills/` with a descriptive name
2. Add a `SKILL.md` file with:
   - Title (first line, as # heading)
   - One-line description (second non-empty line)
   - Detailed instructions
   - Quality standards
   - Output format expectations
3. Optionally add scripts, templates, or reference documents

## Structure

```
skills/
  my-skill/
    SKILL.md          # Required — instructions
    templates/        # Optional — output templates
    scripts/          # Optional — helper scripts
    references/       # Optional — reference docs
```

## Best Practices

- Keep instructions actionable and specific
- Define clear quality criteria
- Include example outputs when possible
- Skills should be self-contained — don't depend on external state
