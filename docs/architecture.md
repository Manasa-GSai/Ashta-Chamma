# Ashta Chamma 3D — System Architecture

This document describes the overall system architecture, data flows, and
component responsibilities for the Ashta Chamma 3D platform.

---

## System Architecture Overview

```mermaid
graph TB
  subgraph Client["Client (Browser)"]
    SPA["React SPA + React Three Fiber"]
  end

  subgraph CDN["CDN / Edge"]
    CF["CloudFront + S3\n(Static Assets)"]
  end

  subgraph AWS["AWS VPC"]
    WAF["AWS WAF"]
    ALB["Application Load Balancer\n(HTTPS / WSS on port 443)"]

    subgraph ECS["ECS Fargate Cluster (Private Subnet)"]
      API1["FastAPI Task 1\n(Uvicorn)"]
      API2["FastAPI Task N\n(Uvicorn)"]
    end

    subgraph Data["Data Layer (Private Subnet)"]
      Redis["ElastiCache Redis\n(Pub/Sub + State Cache)"]
      RDS["RDS PostgreSQL 16\n(Multi-AZ, via RDS Proxy)"]
      SM["Secrets Manager"]
    end

    ECR["ECR\n(Container Registry)"]
  end

  Clerk["Clerk Auth\n(External SaaS)"]

  SPA -->|"HTTPS / WSS"| WAF
  WAF --> ALB
  ALB --> API1
  ALB --> API2
  SPA -->|"Static Assets (HTTPS)"| CF
  SPA -->|"Login / OAuth"| Clerk
  API1 -->|"Verify JWT (JWKS)"| Clerk
  API1 --> Redis
  API2 --> Redis
  API1 --> RDS
  API2 --> RDS
  API1 --> SM
  ECR --> API1
  ECR --> API2
```

---

## WebSocket Real-Time Data Flow

```mermaid
sequenceDiagram
  participant U as User Browser
  participant C as Clerk
  participant A as ALB
  participant F as FastAPI
  participant R as Redis
  participant D as PostgreSQL

  U->>C: Login (email / OAuth)
  C-->>U: JWT (RS256)

  U->>A: POST /api/rooms (Bearer JWT)
  A->>F: Forward request
  F->>D: INSERT INTO rooms
  F->>R: SET room:{id}:state
  F-->>U: {"room_id": "...", "code": "ABC123"}

  U->>A: GET /ws/rooms/{id}?token=JWT (WSS Upgrade)
  A->>F: WebSocket Connect
  F->>R: SUBSCRIBE room:{id}
  F-->>U: state_update (initial snapshot)

  U->>F: {"type": "roll_request"}
  F->>F: Generate cowrie roll (secrets.SystemRandom)
  F->>F: Compute legal moves (MoveValidator)
  F->>R: PUBLISH room:{id} → state_update
  R-->>F: Fan-out to all subscribers (Task 1 + Task N)
  F-->>U: roll_result + move_options

  U->>F: {"type": "select_pawn", "pawn_id": 2}
  F->>F: Validate move (GameStateMachine)
  F->>R: PUBLISH room:{id} → state_update
  F->>R: SET room:{id}:state (checkpoint)
  F-->>U: state_update (new board state)

  Note over F,D: On game end
  F->>D: INSERT INTO game_scores
  F->>R: PUBLISH room:{id} → game_over
  F-->>U: game_over (rankings)
```

---

## Component Responsibilities

```mermaid
graph LR
  subgraph Frontend
    BR["BoardRenderer\n(R3F + Three.js)"]
    CP["CowriePhysics\n(Rapier3D WASM)"]
    PM["PawnManager\n(GLTF + Animations)"]
    HUD["GameHUD\n(React + Zustand)"]
    LB["LobbyUI\n(React + REST)"]
    WS["WebSocketManager\n(Native WS API)"]
    ST["ZustandStore\n(State Mirror)"]
  end

  subgraph Backend
    GSM["GameStateMachine\n(Server-Authoritative FSM)"]
    CRE["CowrieRollEngine\n(secrets.SystemRandom)"]
    MV["MoveValidator\n(Pure Python Rules)"]
    RM["RoomManager\n(CRUD + Lifecycle)"]
    AI["AIEngine\n(Persona-Based Strategy)"]
    WSR["WebSocketRouter\n(FastAPI WS)"]
    REST["RESTRouter\n(FastAPI HTTP)"]
    AUTH["AuthMiddleware\n(Clerk JWT)"]
    PL["PersistenceLayer\n(SQLAlchemy 2.0)"]
    PSB["PubSubBridge\n(aioredis)"]
  end

  WS -->|Game intents| WSR
  LB -->|Room CRUD| REST
  WSR --> GSM
  GSM --> CRE
  GSM --> MV
  GSM --> AI
  WSR --> PSB
  REST --> RM
  REST --> PL
  AUTH --> REST
  AUTH --> WSR
  GSM --> PSB
  PSB -->|Redis pub/sub| PSB
```

---

## Database Schema (Entity Relationships)

```mermaid
erDiagram
  users ||--o{ room_players : "has"
  users ||--o{ game_scores : "earns"
  ai_personas ||--o{ room_players : "plays_as"
  rooms ||--|{ room_players : "contains"
  rooms ||--o{ game_scores : "produces"

  users {
    uuid id PK
    string clerk_id UK
    string display_name
    string avatar_url
    string locale
    timestamp created_at
    timestamp updated_at
  }

  ai_personas {
    serial id PK
    string name
    enum difficulty_level
    jsonb strategy_weights
    boolean is_active
  }

  rooms {
    uuid id PK
    string code UK
    uuid host_user_id FK
    enum status
    int max_players
    timestamp created_at
    timestamp started_at
    timestamp ended_at
  }

  room_players {
    serial id PK
    uuid room_id FK
    uuid user_id FK
    int ai_persona_id FK
    int player_index
    string color
  }

  game_scores {
    serial id PK
    uuid room_id FK
    uuid user_id FK
    int finish_position
    int pawns_captured
    int duration_seconds
  }
```

---

## Infrastructure and Deployment

```mermaid
graph TB
  subgraph CI_CD["CI/CD (GitHub Actions)"]
    GH["Push to main"]
    TEST["Lint + Test"]
    BUILD["Docker Build"]
    PUSH["Push to ECR"]
  end

  subgraph AWS_Prod["AWS Production"]
    subgraph VPC
      subgraph Public["Public Subnet"]
        ALB["ALB (443)"]
        NAT["NAT Gateway"]
      end
      subgraph PrivateA["Private Subnet A"]
        ECS1["Fargate Task"]
        ECS2["Fargate Task"]
      end
      subgraph PrivateB["Private Subnet B"]
        RDS["RDS PostgreSQL\n(Multi-AZ)"]
        Redis["ElastiCache Redis"]
      end
    end
    S3["S3 (SPA Build)"]
    CF["CloudFront"]
    SM["Secrets Manager"]
    CW["CloudWatch + X-Ray"]
  end

  GH --> TEST --> BUILD --> PUSH
  PUSH --> ECS1
  PUSH --> ECS2
  CF --> S3
  ALB --> ECS1
  ALB --> ECS2
  ECS1 --> RDS
  ECS1 --> Redis
  ECS1 --> SM
  ECS2 --> RDS
  ECS2 --> Redis
```

---

## Redis Data Structures

| Key Pattern | Type | Contents | TTL |
|---|---|---|---|
| `room:{id}:state` | Hash | Board positions, current turn, roll result, FSM phase | 24 h |
| `room:{id}:players` | Set | Connected player WebSocket IDs | 24 h |
| `room:{id}:chat` | List | Recent chat messages (capped at 100) | 24 h |
| `session:{clerk_id}` | Hash | Cached Clerk JWT claims | 15 min |

---

## API Endpoint Summary

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/health` | None | Health check |
| `POST` | `/api/rooms` | Required | Create game room |
| `GET` | `/api/rooms/{code}` | Required | Get room info |
| `POST` | `/api/rooms/{code}/join` | Required | Join room |
| `DELETE` | `/api/rooms/{code}/leave` | Required | Leave room |
| `GET` | `/api/scores/leaderboard` | Optional | Leaderboard |
| `GET` | `/api/users/me` | Required | Current user profile |
| `PUT` | `/api/users/me` | Required | Update profile |
| `GET` | `/ws/rooms/{room_id}` | JWT query param | WebSocket game connection |

**OpenAPI (Swagger UI):** `/docs`  
**ReDoc:** `/redoc`

---

## Further Reading

- [ADR-001 — Modernization Strategy](./adr/001-modernization-strategy.md)
- [ADR-002 — Authentication Provider (Clerk)](./adr/002-authentication-provider.md)
- [ADR-003 — Game State Architecture (Server-Authoritative FSM)](./adr/003-game-state-architecture.md)
- [ADR-004 — Real-Time Communication (WebSocket + Redis Pub/Sub)](./adr/004-realtime-communication.md)
- [Runbook — ECS Deployment Rollback](./runbooks/ecs-rollback.md)
- [Runbook — RDS Failover Procedure](./runbooks/rds-failover.md)
- [Runbook — Redis Connection Failure Recovery](./runbooks/redis-recovery.md)
- [Runbook — Debugging WebSocket Disconnections](./runbooks/websocket-debugging.md)
- [Runbook — Manual Room Cleanup](./runbooks/room-cleanup.md)
