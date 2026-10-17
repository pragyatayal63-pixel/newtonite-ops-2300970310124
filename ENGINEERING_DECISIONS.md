# ENGINEERING DECISIONS — NEWTONITE

This document records the foundational engineering decisions made during the architecture and implementation of the **Newtonite Operations Under Pressure** application.

---

## 1. Concurrency Control: Conditional Atomic SQL Updates vs. Application Mutexes

### Context & Problem
Operations systems face high-concurrency race conditions when multiple operators attempt to claim the same unassigned incident or update item attributes concurrently. Using application-level locking (such as threading locks or in-memory state) does not scale horizontally across multiple web worker processes and introduces deadlocks or false positives.

### Options Considered
1. **Pessimistic Locking (`SELECT ... FOR UPDATE`):** Lock the database row upon read, then perform write.
2. **In-Memory Locks / Global Mutex:** Serialize claiming requests in the application memory.
3. **Conditional Atomic SQL Updates (`UPDATE ... WHERE id = :id AND version = :version AND assignee_id IS NULL`):** Leverage PostgreSQL's native transaction isolation and row-level atomicity.

### Chosen Approach
We implemented **Conditional Atomic SQL Updates** coupled with integer **Optimistic Locking (`version`)**.
- For claiming: `UPDATE work_items SET assignee_id = :actor_id, version = version + 1 WHERE id = :id AND version = :v AND assignee_id IS NULL`.
- If another worker claims the item first or modifies the record, `rowcount == 0`. The server immediately rolls back and returns an HTTP `409 Conflict` payload containing the current state to allow client recovery.

### Trade-offs & Limitations
- **Benefits:** No long-lived row lock contention; completely stateless backend horizontally scalable across dozens of instances; zero database deadlocks on read operations.
- **Trade-offs:** Under extreme write contention on the exact same row, competing requests fail fast and require client retries or reloads.

---

## 2. Server-Side Team Isolation & Multi-Tier Authorization

### Context & Problem
Users belong to distinct teams with distinct roles (`VIEWER`, `MEMBER`, `LEAD`, `ADMIN`). A lead in Team A must not have lead permissions (or any read/write visibility) over Team B's items. Client-provided inputs (`team_id`, `role`, `creator_id`) cannot be trusted.

### Options Considered
1. **Client-driven filtering:** Pass user role in the client token/request body and let the UI hide actions.
2. **Global admin roles:** Grant broad permissions across all entities.
3. **Database-backed Team-Scoped Authorization Dependencies:** Server-side dependency injection verifying item ownership and user team membership on every single route.

### Chosen Approach
We implemented centralized FastAPI security dependencies (`require_team_membership`, `get_authorized_item`):
- All listing queries enforce `WHERE team_id IN (authorized_user_team_ids)`.
- Resource mutations fetch the target item and join against `team_members` for the authenticated `user.id`.
- Lead approvals are verified against the specific `team_id` of the work item.

### Trade-offs & Limitations
- **Benefits:** Complete defense-in-depth against IDOR (Insecure Direct Object Reference) and privilege escalation attacks; multi-tenant isolation enforced directly in SQL.
- **Trade-offs:** Additional query lookup for team membership per mutation, optimized via composite index `uq_team_user_membership(team_id, user_id)`.

---

## 3. Idempotent Mutation Handling & Concurrency Race Recovery

### Context & Problem
Under poor network conditions or retry storms, clients re-issue `POST /items` requests with an `Idempotency-Key` header. If two requests with the same key execute simultaneously, both might pass an initial read check before inserting.

### Options Considered
1. **Application-level Cache (Redis / Memory):** Store keys in-memory with short TTL.
2. **Distributed Redis Mutex:** Acquire lock before executing request.
3. **PostgreSQL Unique Constraint with Transactional Commit Collision Recovery:** Store idempotency records with `UNIQUE (user_id, operation, idempotency_key)` and SHA-256 payload fingerprinting inside PostgreSQL.

### Chosen Approach
We implemented PostgreSQL-enforced idempotency records:
- On creation, a SHA-256 hash of the normalized JSON payload is computed.
- If an existing record is found with the same key:
  - If payload hash matches: return cached status and response body.
  - If payload hash differs: raise HTTP `409 Conflict` for key reuse tampering.
- Under concurrent racing requests with the same key, PostgreSQL's `uq_idempotency_user_op_key` constraint guarantees only one transaction commits; the losing transaction catches `IntegrityError`, rolls back cleanly, and re-reads the committed cached result without returning a 500 error to the client.

### Trade-offs & Limitations
- **Benefits:** No external Redis dependency; ACID transactional consistency; immune to app server crashes.
- **Trade-offs:** Requires writing response payloads into PostgreSQL `JSON` columns.

---

## 4. Transactional Outbox Pattern for Asynchronous Events

### Context & Problem
When critical business actions occur (creating an incident, claiming an item, workflow approvals), asynchronous tasks like email alerts or external webhooks must be triggered. Calling external APIs inside the HTTP transaction causes slow responses, timeouts, and two-phase commit inconsistencies (e.g. email sent but DB rolled back, or DB committed but email failed).

### Options Considered
1. **Direct HTTP/SMTP calls inside the route handler:** High risk of network hangs and data inconsistency.
2. **External Message Broker (Kafka / RabbitMQ):** Requires distributed transactions (XA) to align with PostgreSQL commits.
3. **Transactional Outbox Table with PostgreSQL Row Locks (`FOR UPDATE SKIP LOCKED`):** Insert job in the exact same DB transaction as the work item mutation.

### Chosen Approach
We implemented a transactional `outbox_messages` table:
- Work item mutations call `enqueue_outbox_message(db, job_type, payload)` in the same transaction. If the transaction rolls back, no phantom message exists.
- The background outbox worker polls jobs using `SELECT ... FOR UPDATE SKIP LOCKED` with bounded retries and exponential backoff.
- Handlers are designed to be idempotent.

### Trade-offs & Limitations
- **Benefits:** Guarantees at-least-once delivery; zero two-phase commit vulnerability; no extra infrastructure required.
- **Trade-offs:** Relies on polling intervals; does not guarantee exactly-once external delivery (handlers must remain idempotent).

---

## 5. Centralized State Machine Workflow vs. Distributed Controller Logic

### Context & Problem
Work items follow a strict lifecycle (`Open → In Progress → Awaiting Approval → Resolved → Closed`). Skipping steps or unauthorized approvals must be strictly blocked.

### Options Considered
1. **Scattered Endpoint Checks:** Place transition rules inside each API endpoint and React button handler.
2. **Centralized Domain State Machine:** Define transitions and permission matrices in a single declarative service module (`core/workflow.py`).

### Chosen Approach
We implemented a centralized workflow engine:
- Declares allowed state transitions and required roles in `ALLOWED_TRANSITIONS`.
- `validate_workflow_transition()` evaluates state and role permissions before any database write.
- Transitions record audit log entries with `before_state` and `after_state`.

### Trade-offs & Limitations
- **Benefits:** Auditability, maintainability, single source of truth; impossible for an endpoint to bypass transition rules.
- **Trade-offs:** Adding a new workflow state requires updating the centralized map and running tests.
