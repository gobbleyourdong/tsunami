# API Guide

This page documents the REST API. Endpoints follow standard HTTP
semantics — 2xx for success, 4xx for client errors, 5xx for server
errors. All responses are JSON.

## Authentication

All endpoints require a bearer token. Obtain one from the dashboard
and include it in the `Authorization` header:

```http
Authorization: Bearer <your-token>
```

## Rate limits

Requests are limited to 100/min per token. Exceeding the limit returns
HTTP 429 with a `Retry-After` header indicating when you can try again.

## Endpoints

### `GET /v1/items`

List items belonging to the authenticated user. Supports pagination
via `?page=N&per_page=M`. Response body contains `items`, `total`,
`page`, and `per_page`.
