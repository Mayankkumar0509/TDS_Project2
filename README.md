# LLM Analysis Quiz Solver

A production-ready FastAPI service that autonomously solves LLM analysis quizzes. The solver:

- Receives quiz tasks via REST API
- Uses Playwright to render JS-heavy quiz pages
- Extracts task instructions and submit endpoints from DOM
- Downloads and parses data files (PDF, CSV, JSON, images)
- Solves tasks using heuristics (or integrated LLM)
- Submits answers and follows next-URL chains
- Enforces strict 3-minute timeout
- Logs all activity for debugging

## Architecture