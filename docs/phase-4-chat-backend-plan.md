# Phase 4 Chat Backend Plan

Goal: implement authenticated chat thread CRUD plus a stubbed streaming reply, with per-user access control and message persistence after the stream completes.

## Scope

This work covers the backend only:

- list the current user's threads
- create a new thread
- load message history for a thread
- accept AI SDK-style messages for a chat turn
- stream a stubbed assistant reply
- persist the user message and assistant message after streaming finishes
- return `403 Forbidden` when a user accesses another user's thread

## Proposed implementation shape

### 1. Route layer

Add `app/api/chat.py` and include it from `app/main.py`.

Planned endpoints:

- `GET /chat/threads` -> list the current user's threads
- `POST /chat/threads` -> create a thread
- `GET /chat/threads/{id}/messages` -> return ordered message history
- `POST /chat/stream` -> stream a stubbed assistant response

### 2. Auth and ownership checks

Reuse `get_current_user` from `app/auth/dependencies.py`.

Every thread lookup should be scoped by `user_id`.

Behavior:

- if the thread does not exist for the current user, return `404` or `403` depending on the lookup path
- if the thread exists but belongs to a different user, return `403`
- never leak thread or message data across users

### 3. Database helper layer

Add `app/database/chats.py` for typed CRUD helpers.

Likely helpers:

- list threads for a user
- create thread
- fetch a thread by id with ownership check
- fetch messages for a thread with ownership check
- insert messages in a transaction

This keeps route handlers thin and makes the ownership rules easy to test.

### 4. Message format conversion

Add `app/chat/messages.py` to bridge between:

- the AI SDK wire format used by the client
- the internal message representation
- persisted `chat_messages` rows

This should normalize incoming messages before the stream handler uses them.

### 5. Streaming stub

Add `app/chat/streaming.py` and `app/chat/orchestrator.py`.

The stream should:

- accept the incoming message payload
- produce a stub assistant response incrementally
- collect the final assistant text on the server
- persist the user and assistant messages only after the stream completes

No LLM call yet. The purpose is to prove the lifecycle and persistence flow.

### 6. Persistence timing

Persist messages only after the stream finishes successfully.

That means:

- user message is not written before the stream starts
- assistant message is not written until the final streamed text is known
- both messages are stored together after completion

This keeps the initial implementation simple and avoids partial turn records.

## Test plan

Add focused tests for the risky behavior first:

- list threads only returns the current user's records
- create thread assigns the current user as owner
- message history is ordered and scoped to the thread owner
- accessing another user's thread returns `403`
- stream endpoint emits stubbed text and persists both messages after completion

## Suggested delivery order

1. Add the chat router and wire it into the app.
2. Add the database helpers and ownership checks.
3. Add the message conversion and streaming skeleton.
4. Add tests for `403` access control and post-stream persistence.
5. Hook up the route to the stubbed stream response.

## Out of scope for this phase

- retrieval or grounding
- real LLM calls
- citations
- thread title generation
- frontend integration

If you want, I can implement this next and keep the file in sync as the code lands.
