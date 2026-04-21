# API Reference

Documents endpoints, parameters, and responses. Everything a caller
needs to hit the API correctly is here — but the project lacks an
index.md or intro.md, so users landing at the site root see nothing.

## GET /items

Returns all items.

## POST /items

Creates a new item.

## DELETE /items/:id

Deletes the item with the given id. Returns 404 if it doesn't exist.
