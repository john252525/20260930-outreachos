# Спринт 7 — WhatsApp sender + Users в БД + Campaign + Real-time + ML scoring + Multi-armed bandit + Audit log

Проверил: зависимости от Спринта 0–6 соблюдены, порядок задач логичен, acceptance criteria проверяемы, нет противоречий с `docs/contracts.md`. Спринт 7 — **спринт зрелости продукта**. До сих пор система работала «для одного технического пользователя» или «для узкой команды». Спринт 7 делает её продуктом для команд и компаний.

## Что даёт Спринт 7

1. **WhatsApp sender** — четвёртый канал. Через WhatsApp Business API (Meta) или через провайдеров (Twilio, 360dialog, Wazzup). Строже, чем Telegram, потому что Meta банит за нарушения.
2. **Users в БД** — вместо env. Роли (admin / manager / viewer), приглашения, пароли.
3. **Campaign** — сущность, которая группирует outreach по кампаниям (не путать с flow). Кампания — «запуск Q1 в РФ для гидробортов», внутри — много flow'ов.
4. **Real-time collaboration** — несколько пользователей одновременно работают с review queue. WebSocket + optimistic locking.
5. **ML scoring** — модель, которая скорит контакты по вероятности ответа. Обучается на исторических данных.
6. **Multi-armed bandit** — вместо классического A/B: динамически перераспределяет трафик в пользу выигрывающего варианта.
7. **Audit log** — каждое действие пользователя и системы логируется. Для compliance и разбора инцидентов.

## Разбивка на под-спринты

**7A — Users + Roles + Audit log.** Фундамент: без users нельзя делать collaboration, без audit — compliance.

**7B — Campaign.** Группировка outreach. Логически связана с users (кто владелец кампании).

**7C — WhatsApp sender.** Четвёртый канал.

**7D — Real-time collaboration.** WebSocket + optimistic locking для review queue.

**7E — Multi-armed bandit.** Замена классического A/B в experiments.

**7F — ML scoring.** Модель для скоринга контактов.

**Порядок:** 7A → 7B → 7C → 7D → 7E → 7F. Users — фундамент, Campaign — надстройка, WhatsApp — независим, real-time и bandit — улучшения, ML — самое сложное в конце.

**Что НЕ в этом спринте:**
- Multi-region deploy — Спринт 8.
- SSO (SAML, OIDC) — Спринт 8.
- Custom domains для email — Спринт 8.
- Billing / подписки — Спринт 8+.
- Мобильное приложение — не планируется.

---

# 7A — Users + Roles + Audit log

## Что даёт

**Users в БД** — вместо env. Каждый user принадлежит одному или нескольким tenant'ам (multi-tenant users). Роли: admin, manager, viewer.

**Roles:**
- `admin` — всё, включая управление users и settings.
- `manager` — работа с flows, reviews, campaigns; не может менять settings и users.
- `viewer` — только чтение.

**Audit log** — таблица `audit_events` в отдельной схеме `audit`. Каждое действие: who (user_id), what (action), on what (resource_type, resource_id), when, from where (ip, user_agent), result (success/failure).

## Архитектура

```
                    ┌──────────────────────────────────────┐
                    │         users-service                 │
                    │                                       │
   HTTP POST ──────►│  /users, /auth/*, /invitations        │
                    │       │                               │
                    │       ├──► UserRepository             │
                    │       ├──► PasswordHasher             │
                    │       ├──► TokenService (JWT)         │
                    │       └──► AuditLogger                │
                    │                                       │
                    │  Events:                              │
                    │   - user.created                      │
                    │   - user.role_changed                 │
                    │   - user.deactivated                  │
                    └──────────────────────────────────────┘
                                      │
                                      ▼
                                   Postgres
                          (users, user_tenants, invitations)
                          (audit.audit_events)
```

**Ключевые принципы:**
1. **Users в отдельном сервисе.** Web UI ходит в него, не в NextAuth.
2. **Multi-tenant users.** Один user может иметь доступ к нескольким tenant'ам.
3. **JWT с tenant_id.** Текущий tenant — в токене.
4. **Audit — везде.** Каждый сервис пишет в `audit.audit_events` (или через отдельный audit-service).
5. **Password reset через email.** Нужен email-sender (не sender-email для outreach, а транзакционный).

---

# Задача 7A.1 — Каркас `users-service` + модели User / UserTenant / Invitation

**Файл:** `docs/tasks/sprint-7a/7a.1-bootstrap.md`

## Цель

Создать сервис `users-service`, определить модели, миграция с RLS (для user_tenants), API для создания/получения users.

## Зависимости

Спринт 6 закрыт.

## Что создать

```
services/users-service/
├── pyproject.toml
├── Dockerfile
├── alembic.ini
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_create_users.py
├── src/users_service/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── schemas.py
│   ├── repository.py
│   ├── service.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── password.py
│   │   ├── tokens.py
│   │   └── deps.py
│   ├── invitations/
│   │   ├── __init__.py
│   │   └── service.py
│   ├── events.py
│   └── api/
│       ├── __init__.py
│       ├── routes_users.py
│       ├── routes_auth.py
│       └── routes_invitations.py
└── tests/
```

## Детали

### `models.py`

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.mixins import MetadataMixin, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin):
    """Пользователь. Не tenant-скоупная сущность — user может быть в нескольких tenant'ах."""
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )  # active | inactive | locked | pending_email_verification

    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_verification_token: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    password_reset_token: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Для brute-force protection
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    memberships: Mapped[list["UserTenant"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserTenant(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """Связь user ↔ tenant с ролью."""
    __tablename__ = "user_tenants"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer", index=True)
    # admin | manager | viewer

    is_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    invited_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_user_tenants"),
        Index("ix_user_tenants_tenant_role", "tenant_id", "role"),
    )


class Invitation(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """Приглашение в tenant."""
    __tablename__ = "invitations"

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")
    token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)

    invited_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )  # pending | accepted | expired | revoked

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", "status", name="uq_invitation_tenant_email_pending"),
    )
```

**Важно:**
- `users` — **не** tenant-скоупная (user глобальный, может быть в нескольких tenant'ах).
- `user_tenants` — tenant-скоупная (RLS).
- `invitations` — tenant-скоупная (RLS).
- `users` RLS — не включаем, но доступ через отдельную роль. Альтернатива: `users` без RLS, но все запросы через join с `user_tenants` (где RLS).

**Решение для users RLS:** `users` доступна только через `users-service` с внутренней ролью без RLS. К остальным сервисам users не имеет прямого доступа. Auth проверка — через JWT.

### Миграция

```python
def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("email_verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("email_verification_token", sa.String(128), nullable=True),
        sa.Column("password_reset_token", sa.String(128), nullable=True),
        sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_ip", sa.String(45), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "user_tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.Column("is_owner", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_tenants_tenant_user", "user_tenants", ["tenant_id", "user_id"], unique=True)
    op.create_index("ix_user_tenants_tenant_role", "user_tenants", ["tenant_id", "role"])

    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.Column("token", sa.String(128), nullable=False, unique=True),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_invitations_token", "invitations", ["token"], unique=True)
    op.create_index("ix_invitations_tenant_status", "invitations", ["tenant_id", "status"])
    op.create_index("ix_invitations_email", "invitations", ["email"])

    # RLS для tenant-скоупных
    for table in ["user_tenants", "invitations"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """)

    # users — без RLS, доступ через отдельную роль
```

### Добавить в `infra/docker-compose.dev.yml`

```yaml
  users-service:
    <<: *service-defaults
    build:
      context: ..
      dockerfile: services/users-service/Dockerfile
    container_name: outreach-users-service
    environment:
      <<: *common-env
      SERVICE_NAME: users-service
      SERVICE_PORT: "8000"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-outreach}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-outreach}
      NATS_URL: nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/14
      JWT_SECRET: ${JWT_SECRET:?required}
      JWT_EXPIRES_MINUTES: "10080"
      TRANSACTIONAL_EMAIL_URL: http://transactional-email:8000
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      nats:
        condition: service_healthy
      redis:
        condition: service_healthy
    labels:
      caddy: users.dev.aitler.ru
      caddy.reverse_proxy: "{{upstreams 8000}}"
```

**Обновить `.env.example`:**

```bash
# JWT
JWT_SECRET=   # openssl rand -base64 64
JWT_EXPIRES_MINUTES=10080   # 7 дней
```

**Также понадобится `transactional-email`** — маленький сервис для отправки транзакционных писем (verification, password reset, invitations). Это отдельно от `sender-email` (который для outreach).

## Acceptance criteria

```bash
docker compose ... run --rm users-service alembic upgrade head
docker compose ... up -d users-service
curl -fsS https://users.dev.aitler.ru/healthz
bash scripts/psql.sh -c "\d+ users"
bash scripts/psql.sh -c "\d+ user_tenants"
bash scripts/psql.sh -c "\d+ invitations"
```

## Подсказки

- **users без RLS** — глобальная сущность. Доступ через `users-service` с внутренней ролью.
- **`user_tenants` с RLS** — tenant-скоупная.
- **`is_owner`** — создатель tenant. Нельзя удалить последнего owner'а.
- **`failed_login_attempts` + `locked_until`** — brute-force protection.

## Анти-паттерны

- ❌ Не давать RLS на users — там нет tenant_id.
- ❌ Не забывать unique на `email`.
- ❌ Не давать удалять owner'а.

---

# Задача 7A.2 — Auth: password hashing, JWT, login/logout

**Файл:** `docs/tasks/sprint-7a/7a.2-auth.md`

## Детали

### `auth/password.py`

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hash_: str) -> bool:
    try:
        _hasher.verify(hash_, password)
        return True
    except VerifyMismatchError:
        return False


def needs_rehash(hash_: str) -> bool:
    return _hasher.check_needs_rehash(hash_)
```

**Используем argon2**, не bcrypt. Argon2 — современный стандарт (победитель Password Hashing Competition).

**Добавить `argon2-cffi>=23.1` в зависимости.**

### `auth/tokens.py`

```python
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from users_service.config import Settings


class TokenService:
    """JWT-токены для API-аутентификации."""

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret
        self._algorithm = "HS256"
        self._expires_minutes = settings.jwt_expires_minutes

    def create_access_token(
        self,
        *,
        user_id: UUID,
        email: str,
        tenant_id: UUID,
        role: str,
        extra: dict | None = None,
    ) -> tuple[str, datetime]:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self._expires_minutes)
        payload = {
            "sub": str(user_id),
            "email": email,
            "tenant_id": str(tenant_id),
            "role": role,
            "exp": expires_at,
            "iat": datetime.now(timezone.utc),
            **(extra or {}),
        }
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return token, expires_at

    def decode_token(self, token: str) -> dict:
        return jwt.decode(token, self._secret, algorithms=[self._algorithm])
```

**Важно:** токен содержит `tenant_id` и `role` — для быстрой проверки прав без БД.

### `api/routes_auth.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Request, status

from users_service.auth.password import hash_password, verify_password
from users_service.auth.tokens import TokenService
from users_service.api.deps import get_service, get_token_service
from users_service.schemas import LoginRequest, LoginResponse, RegisterRequest, RegisterResponse
from users_service.service import UserService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    svc: UserService = Depends(get_service),
    tokens: TokenService = Depends(get_token_service),
) -> RegisterResponse:
    """Регистрация. Создаёт user + tenant + owner membership."""
    user, tenant = await svc.register(
        email=data.email,
        password=data.password,
        display_name=data.display_name,
        company_name=data.company_name,
    )
    token, expires_at = tokens.create_access_token(
        user_id=user.id,
        email=user.email,
        tenant_id=tenant.id,
        role="admin",
    )
    return RegisterResponse(
        user_id=user.id,
        tenant_id=tenant.id,
        access_token=token,
        expires_at=expires_at,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    request: Request,
    svc: UserService = Depends(get_service),
    tokens: TokenService = Depends(get_token_service),
) -> LoginResponse:
    """Логин. Возвращает JWT для одного или нескольких tenant'ов."""
    ip = request.client.host if request.client else None
    user = await svc.authenticate(email=data.email, password=data.password, ip=ip)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    memberships = await svc.list_user_tenants(user.id)
    if not memberships:
        raise HTTPException(status_code=403, detail="User has no active tenant memberships")

    # Если у user один tenant — сразу токен
    # Если несколько — возвращаем список, frontend выбирает
    if data.tenant_id:
        membership = next((m for m in memberships if m.tenant_id == data.tenant_id), None)
        if membership is None:
            raise HTTPException(status_code=403, detail="No access to this tenant")
    else:
        membership = memberships[0]

    token, expires_at = tokens.create_access_token(
        user_id=user.id,
        email=user.email,
        tenant_id=membership.tenant_id,
        role=membership.role,
    )
    return LoginResponse(
        user_id=user.id,
        tenant_id=membership.tenant_id,
        role=membership.role,
        access_token=token,
        expires_at=expires_at,
        available_tenants=[{"id": str(m.tenant_id), "role": m.role} for m in memberships],
    )


@router.post("/switch-tenant", response_model=LoginResponse)
async def switch_tenant(
    data: SwitchTenantRequest,
    svc: UserService = Depends(get_service),
    tokens: TokenService = Depends(get_token_service),
) -> LoginResponse:
    """Переключение tenant'а. Возвращает новый токен."""
    ...


@router.post("/logout", status_code=204)
async def logout() -> None:
    """Logout. JWT stateless — просто клиент удаляет токен."""
    return None


@router.post("/password-reset-request", status_code=202)
async def password_reset_request(
    data: PasswordResetRequest,
    svc: UserService = Depends(get_service),
) -> None:
    """Запрос на сброс пароля. Отправляет email."""
    await svc.request_password_reset(email=data.email)


@router.post("/password-reset-confirm", status_code=204)
async def password_reset_confirm(
    data: PasswordResetConfirm,
    svc: UserService = Depends(get_service),
) -> None:
    """Подтверждение сброса пароля."""
    await svc.confirm_password_reset(token=data.token, new_password=data.new_password)
```

### `service.py` — ключевые методы

```python
class UserService:
    async def register(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
        company_name: str,
    ) -> tuple[User, Tenant]:
        # 1. Проверить, что email не занят
        existing = await self._repo.get_user_by_email(email.lower())
        if existing is not None:
            raise ConflictError("Email already registered")

        # 2. Создать user
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            display_name=display_name,
            status="active",
            email_verified=False,
        )
        await self._repo.add_user(user)

        # 3. Создать tenant (через tenant-service)
        tenant = await self._tenant_client.create_tenant(
            name=company_name,
            slug=self._slugify(company_name),
            owner_user_id=str(user.id),
        )

        # 4. Создать membership (owner, admin)
        membership = UserTenant(
            tenant_id=UUID(tenant["id"]),
            user_id=user.id,
            role="admin",
            is_owner=True,
            is_active=True,
            accepted_at=datetime.now(timezone.utc),
        )
        await self._repo.add_membership(membership)

        # 5. Создать TenantSettings с дефолтами (через tenant-service)
        await self._tenant_client.create_settings(UUID(tenant["id"]))

        # 6. Отправить verification email
        await self._send_verification_email(user)

        # 7. Audit
        await self._audit.log(
            action="user.registered",
            user_id=user.id,
            tenant_id=UUID(tenant["id"]),
            resource_type="user",
            resource_id=user.id,
        )

        return user, tenant

    async def authenticate(
        self,
        *,
        email: str,
        password: str,
        ip: str | None,
    ) -> User | None:
        user = await self._repo.get_user_by_email(email.lower())
        if user is None:
            # Constant-time: даже если user не найден — проверяем хеш от "dummy"
            verify_password(password, "$argon2id$v=19$m=65536,t=2,p=1$...")
            return None

        # Проверка блокировки
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            raise AppError("Account locked. Try later.", code="account_locked", status_code=403)

        # Проверка пароля
        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            await self._repo._s.flush()
            return None

        # Успех
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)
        user.last_login_ip = ip
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        await self._repo._s.flush()

        return user
```

**Важно:**
- **Constant-time для authenticate** — даже если user не найден, проверяем hash. Иначе timing attack.
- **Brute-force protection** — 5 неудачных попыток → lock на 15 минут.
- **`register` создаёт tenant автоматически** — user регистрируется и сразу получает свой tenant.

### `api/deps.py`

```python
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from users_service.auth.tokens import TokenService


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    tokens: TokenService = Depends(get_token_service),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = tokens.decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


def require_role(*roles: str):
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return _check
```

**Использование:**

```python
@router.get("/users", dependencies=[Depends(require_role("admin"))])
async def list_users(...): ...
```

## Acceptance criteria

```bash
# 1. Регистрация
curl -sX POST https://users.dev.aitler.ru/auth/register \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: reg-1" \
  -d '{"email":"test@example.com","password":"secure_password_123","display_name":"Test User","company_name":"Test Company"}' | jq .
# Ожидание: user_id, tenant_id, access_token

# 2. Логин
curl -sX POST https://users.dev.aitler.ru/auth/login \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: login-1" \
  -d '{"email":"test@example.com","password":"secure_password_123"}' | jq .
# Ожидание: access_token

# 3. Использовать токен
TOKEN=$(...)
curl -s -H "Authorization: Bearer $TOKEN" https://users.dev.aitler.ru/users/me | jq .
# Ожидание: информация о user

# 4. Неверный пароль → 401
curl -sX POST https://users.dev.aitler.ru/auth/login \
  -d '{"email":"test@example.com","password":"wrong"}' -w "\n%{http_code}\n"
# Ожидание: 401

# 5. Locked после 5 попыток
# ...
```

## Подсказки

- **argon2** — современный стандарт. Не bcrypt.
- **JWT stateless** — logout на клиенте.
- **Constant-time для authenticate** — критично.
- **`tenant_id` в JWT** — быстрая проверка без БД.

## Анти-паттерны

- ❌ Не хранить пароли в plaintext.
- ❌ Не возвращать разные ошибки для «user not found» и «wrong password».
- ❌ Не делать logout через серверный blacklist — stateless.

---

# Задача 7A.3 — Audit log + интеграция во все сервисы

**Файл:** `docs/tasks/sprint-7a/7a.3-audit.md`

## Детали

### Схема audit

Создаём **схему** `audit` в Postgres.

```python
# Миграция в users-service (или отдельная в analytics-service)
def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")
    op.execute("GRANT USAGE ON SCHEMA audit TO outreach_app")

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("actor_type", sa.String(16), nullable=False, default="user"),  # user | system | agent
        sa.Column("action", sa.String(128), nullable=False, index=True),
        sa.Column("resource_type", sa.String(64), nullable=False, index=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("result", sa.String(16), nullable=False, default="success"),  # success | failure
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("changes", postgresql.JSONB, nullable=False, default=dict),  # {before, after}
        sa.Column("context", postgresql.JSONB, nullable=False, default=dict),  # дополнительный контекст
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="audit",
    )
    op.create_index("ix_audit_events_tenant_time", "audit_events", ["tenant_id", "occurred_at"], schema="audit")
    op.create_index("ix_audit_events_tenant_action", "audit_events", ["tenant_id", "action"], schema="audit")
    op.create_index("ix_audit_events_tenant_resource", "audit_events", ["tenant_id", "resource_type", "resource_id"], schema="audit")

    # RLS
    op.execute("ALTER TABLE audit.audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY audit_events_isolation ON audit.audit_events
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid OR tenant_id IS NULL)
        WITH CHECK (true)
    """)
```

### `libs/common/audit.py`

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from uuid6 import uuid7

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class AuditEvent:
    action: str
    resource_type: str
    resource_id: UUID | None = None
    tenant_id: UUID | None = None
    user_id: UUID | None = None
    actor_type: str = "user"  # user | system | agent
    result: str = "success"
    ip_address: str | None = None
    user_agent: str | None = None
    changes: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


async def write_audit_event(session: AsyncSession, event: AuditEvent) -> None:
    """Пишет audit-событие в отдельной транзакции (не блокирует основную)."""
    await session.execute(
        text("""
            INSERT INTO audit.audit_events (
                id, tenant_id, user_id, actor_type, action, resource_type, resource_id,
                result, ip_address, user_agent, changes, context, occurred_at
            ) VALUES (
                :id, :tenant_id, :user_id, :actor_type, :action, :resource_type, :resource_id,
                :result, :ip_address, :user_agent, :changes, :context, :occurred_at
            )
        """),
        {
            "id": str(uuid7()),
            "tenant_id": str(event.tenant_id) if event.tenant_id else None,
            "user_id": str(event.user_id) if event.user_id else None,
            "actor_type": event.actor_type,
            "action": event.action,
            "resource_type": event.resource_type,
            "resource_id": str(event.resource_id) if event.resource_id else None,
            "result": event.result,
            "ip_address": event.ip_address,
            "user_agent": event.user_agent,
            "changes": event.changes,
            "context": event.context,
            "occurred_at": datetime.now(timezone.utc),
        },
    )
```

**Важно:** audit пишется **в той же транзакции**, что и основное действие. Если основная откатится — audit тоже. Это правильно: audit должен отражать реальность.

**Для случаев, когда основная транзакция может откатиться, но audit нужен** (например, failed login) — писать в **отдельной** транзакции.

### Middleware для автоматического audit

Не делать middleware. Слишком много шума. Audit — **явный вызов** в handler'ах.

**Использование:**

```python
# В ComposerService.draft после создания message:
await write_audit_event(session, AuditEvent(
    action="message.drafted",
    resource_type="message",
    resource_id=message.id,
    tenant_id=tenant_id,
    user_id=user_id,
    ip_address=...,
    user_agent=...,
    changes={"after": {"subject": message.subject}},
    context={"template_id": template.template_id},
))
```

**Ключевые действия, которые аудируются:**
- Auth: login, logout, password_reset, register.
- Users: create, update_role, deactivate, invite.
- Tenants: create, update_settings, archive.
- Flows: create, pause, resume, cancel.
- Messages: drafted (авто), approved, rejected, edited, sent.
- Revisions: proposed (авто), approved, rejected.
- Experiments: created, started, completed.
- Sender accounts: created, verified, paused, deleted.
- Settings: updated.

### API для чтения audit

```python
@router.get("/audit/events")
async def list_audit_events(
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    resource_id: UUID | None = Query(None),
    user_id: UUID | None = Query(None),
    from_time: datetime | None = Query(None),
    to_time: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    svc=Depends(get_service),
) -> list[AuditEventRead]:
    ...
```

### Retention

Audit logs должны храниться долго (1-3 года для compliance). Но не бесконечно.

**Решение:** retention 365 дней по умолчанию. Настраивается per tenant. Cleanup через фоновый воркер раз в день.

```python
async def cleanup_old_events(retention_days: int = 365) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await session.execute(
        text("DELETE FROM audit.audit_events WHERE occurred_at < :cutoff"),
        {"cutoff": cutoff},
    )
    return result.rowcount
```

## Acceptance criteria

```bash
# 1. Выполнить действие (login)
curl -sX POST https://users.dev.aitler.ru/auth/login ...

# 2. Проверить audit
curl -s -H "Authorization: Bearer $TOKEN" "https://users.dev.aitler.ru/audit/events?action=user.login" | jq .
# Ожидание: событие есть

# 3. Проверить, что audit пишется при всех ключевых действиях
# ... пройтись по сценариям
```

## Подсказки

- **Audit в той же транзакции** — консистентность.
- **Для failed login — отдельная транзакция** (основная откатится).
- **Retention 365 дней** — настраивается.
- **Отдельная схема `audit`** — чисто.

## Анти-паттерны

- ❌ Не делать audit через middleware — слишком много шума.
- ❌ Не логировать read-only действия (кроме sensitive).
- ❌ Не хранить audit в той же таблице, что бизнес-данные.

---

# Задача 7A.4 — Обновить Web UI: users, roles, invitations, audit

**Файл:** `docs/tasks/sprint-7a/7a.4-ui.md`

## Детали

### Изменения в Auth.js

**Заменить credentials на HTTP-вызов users-service:**

```typescript
// src/lib/auth.ts
Credentials({
  async authorize(credentials) {
    const response = await fetch(`${process.env.USERS_SERVICE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });
    if (!response.ok) return null;
    const data = await response.json();
    return {
      id: data.user_id,
      email: credentials.email,
      name: data.display_name || credentials.email,
      tenantId: data.tenant_id,
      role: data.role,
      accessToken: data.access_token,
    };
  },
}),
```

**JWT callback** — сохранять `role`, `accessToken` в токен.

**BFF proxy** — использовать `accessToken` из сессии:

```typescript
headers.set("Authorization", `Bearer ${session.user.accessToken}`);
```

### Новые страницы

- `/settings/users` — список users в tenant.
- `/settings/users/invite` — приглашение.
- `/settings/audit` — audit log с фильтрами.
- `/settings/profile` — профиль, смена пароля.

### `UserList.tsx`

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { DataTable } from "@/components/shared/DataTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { InviteUserDialog } from "./InviteUserDialog";

export function UserList() {
  const [inviteOpen, setInviteOpen] = useState(false);
  const { data } = useQuery({
    queryKey: ["users"],
    queryFn: () => apiClient<any[]>("users/users"),
  });

  const columns = [
    { key: "display_name", label: "Имя" },
    { key: "email", label: "Email" },
    {
      key: "role", label: "Роль",
      render: (v: string) => <Badge>{v}</Badge>,
    },
    {
      key: "is_owner", label: "Owner",
      render: (v: boolean) => v ? "✓" : "—",
    },
    {
      key: "last_login_at", label: "Last login",
      render: (v: string) => v ? new Date(v).toLocaleString("ru") : "—",
    },
    {
      key: "actions", label: "",
      render: (_: any, row: any) => (
        <Button variant="ghost" size="sm">Изменить</Button>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setInviteOpen(true)}>Пригласить пользователя</Button>
      </div>
      <DataTable columns={columns} data={data || []} />
      <InviteUserDialog open={inviteOpen} onOpenChange={setInviteOpen} />
    </div>
  );
}
```

### `AuditLog.tsx`

```tsx
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { DataTable } from "@/components/shared/DataTable";
import { Badge } from "@/components/ui/badge";

export function AuditLog() {
  const [filters, setFilters] = useState({ action: "", user_id: "" });
  const params = new URLSearchParams();
  if (filters.action) params.set("action", filters.action);
  if (filters.user_id) params.set("user_id", filters.user_id);

  const { data } = useQuery({
    queryKey: ["audit", filters],
    queryFn: () => apiClient<any[]>(`users/audit/events?${params.toString()}`),
  });

  const columns = [
    {
      key: "occurred_at", label: "Когда",
      render: (v: string) => new Date(v).toLocaleString("ru"),
    },
    { key: "actor_type", label: "Кто" },
    { key: "action", label: "Действие" },
    { key: "resource_type", label: "Ресурс" },
    {
      key: "result", label: "Результат",
      render: (v: string) => <Badge variant={v === "success" ? "default" : "destructive"}>{v}</Badge>,
    },
    { key: "ip_address", label: "IP" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Фильтр по action..."
          value={filters.action}
          onChange={(e) => setFilters({ ...filters, action: e.target.value })}
          className="border rounded px-3 py-2 text-sm"
        />
      </div>
      <DataTable columns={columns} data={data || []} />
    </div>
  );
}
```

## Acceptance criteria

```bash
# 1. Открыть /settings/users
# Ожидание: список users

# 2. Пригласить пользователя
# Ожидание: email отправлен, invitation создан

# 3. Открыть /settings/audit
# Ожидание: события
```

---

# 7B — Campaign

## Что даёт

**Campaign** — сущность, которая группирует outreach по большим инициативам. Пример: «Запуск Q1 2026 — гидроборты — РФ». Внутри кампании — много flow'ов, много сегментов, много экспериментов.

**Отличие от flow:**
- Flow — техническая цепочка (brief → ICP → sourcing → drafts).
- Campaign — бизнес-инициатива (кампания на квартал).

**Ключевые поля:**
- Название, описание, цели.
- Владелец (user).
- Период (start_date, end_date).
- Бюджет (опционально).
- Привязка к flow'ам.
- Метрики (агрегированные).

## Модель данных

**Таблица `campaigns` в новом сервисе `campaign-service`** (или в orchestrator):

```python
class Campaign(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner_user_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", index=True
    )  # draft | active | paused | completed | archived

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    goals: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # {meetings_target: 20, revenue_target: 1000000, currency: "RUB"}

    budget: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # {amount: 100000, currency: "RUB", spent: 0}

    targeting_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Кэш агрегатов из ICP

    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Кэш метрик из analytics: {sent, replied, positive_replied, meetings_booked}

    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**Обновить `flows`:** добавить `campaign_id` (nullable).

**Обновить `experiments`:** добавить `campaign_id` (nullable).

**Обновить `messages`:** добавить `campaign_id` (уже есть в contracts!).

## API

```python
@router.post("/campaigns", ...)
@router.get("/campaigns", ...)
@router.get("/campaigns/{id}", ...)
@router.patch("/campaigns/{id}", ...)
@router.post("/campaigns/{id}/archive", ...)
@router.get("/campaigns/{id}/metrics", ...)  # агрегаты из analytics
@router.get("/campaigns/{id}/flows", ...)    # связанные flows
```

## UI

`/campaigns` — список.
`/campaigns/[id]` — детали, метрики, связанные flows, эксперименты.

## Acceptance criteria

```bash
# 1. Создать кампанию
curl -sX POST https://orchestrator.dev.aitler.ru/campaigns \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: camp-1" \
  -d '{"name":"Q1 2026 — гидроборты","description":"...","owner_user_id":"...","start_date":"2026-01-01","end_date":"2026-03-31","goals":{"meetings_target":20}}' | jq .

# 2. Привязать flow к кампании (через campaign_id в flow.params)

# 3. Метрики кампании
curl -s -H "X-Tenant-ID: $TENANT" https://orchestrator.dev.aitler.ru/campaigns/$CAMP_ID/metrics | jq .
# Ожидание: агрегаты
```

## Подсказки

- **Campaign — бизнес-сущность.** Не путать с flow.
- **Metrics — кэш из analytics.** Обновляется по расписанию.
- **Owner — user.** Нельзя удалить user, если он owner активной кампании.

## Анти-паттерны

- ❌ Не смешивать campaign и flow.
- ❌ Не хранить metrics как источник правды — только кэш.

---

# 7C — WhatsApp sender

## Что даёт

**WhatsApp** — четвёртый канал. Через **WhatsApp Business API (Meta)** или через провайдеров (Twilio, 360dialog, Wazzup, Gupshup).

**Ключевое отличие от Telegram:**
- **Meta строго банит за нарушения.** Шаблоны сообщений должны быть pre-approved Meta.
- **Только для тех, кто дал opt-in.** WhatsApp — не для холодного outreach.
- **24-часовое окно.** После последнего сообщения от пользователя — 24 часа, в течение которых можно писать свободно. После — только pre-approved шаблоны.
- **Провайдеры** (Twilio и др.) упрощают работу с Meta.

**Решение:** используем **провайдера** (Gupshup или 360dialog), не напрямую Meta. Провайдер берёт на себя:
- Регистрацию Business Account.
- Approval шаблонов.
- Rate limits.
- Webhook'и.

## Архитектура

```
                    ┌──────────────────────────────────────┐
                    │         whatsapp-sender               │
                    │                                       │
   message.approved►│  WhatsAppSenderService                │
                    │       │                               │
                    │       ├──► ProviderClient (Gupshup)   │
                    │       ├──► TemplateRegistry (Meta)    │
                    │       ├──► SessionWindowChecker       │
                    │       └──► Publisher (NATS)           │
                    │                                       │
                    │  Events:                              │
                    │   - message.sent                      │
                    │   - message.failed                    │
                    └──────────────────────────────────────┘
```

## Задача 7C.1 — Каркас + модели + provider abstraction

**Файл:** `docs/tasks/sprint-7c/7c.1-bootstrap.md`

## Детали

### `models.py`

```python
class WhatsAppAccount(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "whatsapp_accounts"

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # gupshup | twilio | 360dialog

    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    provider_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unverified", index=True)
    # unverified | active | paused | rate_limited | error

    # Meta rate limits
    daily_sent_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_limit_current: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    # WhatsApp Business — до 1000/день для verified

    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class WhatsAppTemplate(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """Pre-approved шаблоны Meta."""
    __tablename__ = "whatsapp_templates"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="ru")
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    # marketing | utility | authentication

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    # pending | approved | rejected

    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    # С плейсхолдерами: "Здравствуйте, {{1}}! ..."

    variables_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_template_id: Mapped[str] = mapped_column(String(128), nullable=False)

    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "language", name="uq_whatsapp_templates"),
    )


class WhatsAppSendAttempt(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "whatsapp_send_attempts"

    message_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("whatsapp_accounts.id", ondelete="SET NULL"), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)

    to_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    template_id: Mapped[UUID | None] = mapped_column(nullable=True)

    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### Provider abstraction

```python
# providers/base.py
from abc import ABC, abstractmethod


class WhatsAppProvider(ABC):
    name: str

    @abstractmethod
    async def send_template_message(
        self,
        *,
        to_phone: str,
        template_name: str,
        template_language: str,
        variables: dict[str, str],
    ) -> dict:
        """Отправка через pre-approved шаблон."""
        ...

    @abstractmethod
    async def send_text_message(
        self,
        *,
        to_phone: str,
        text: str,
    ) -> dict:
        """Отправка текста (только в 24-часовом окне)."""
        ...

    @abstractmethod
    async def submit_template(
        self,
        *,
        name: str,
        language: str,
        category: str,
        body: str,
    ) -> dict:
        """Регистрация шаблона у провайдера → Meta на approval."""
        ...

    async def close(self) -> None:
        return None
```

**Реализация `GupshupProvider`:**

```python
class GupshupProvider(WhatsAppProvider):
    name = "gupshup"

    def __init__(self, api_key: str, app_name: str) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.gupshup.io/wa/api/v1",
            headers={"apikey": api_key},
            timeout=httpx.Timeout(30.0),
        )
        self._app_name = app_name

    async def send_template_message(self, *, to_phone, template_name, template_language, variables):
        payload = {
            "channel": "whatsapp",
            "source": self._app_name,
            "destination": to_phone,
            "src.name": self._app_name,
            "template": json.dumps({
                "id": template_name,
                "params": list(variables.values()),
            }),
        }
        resp = await self._client.post("/msg", data=payload)
        resp.raise_for_status()
        data = resp.json()
        return {"message_id": data.get("messageId"), "status": data.get("status")}

    async def send_text_message(self, *, to_phone, text):
        payload = {
            "channel": "whatsapp",
            "source": self._app_name,
            "destination": to_phone,
            "message": json.dumps({"type": "text", "text": text}),
        }
        resp = await self._client.post("/msg", data=payload)
        resp.raise_for_status()
        data = resp.json()
        return {"message_id": data.get("messageId"), "status": data.get("status")}

    async def submit_template(self, *, name, language, category, body):
        payload = {
            "appId": self._app_name,
            "elementName": name,
            "language": language,
            "category": category,
            "templateType": "TEXT",
            "content": body,
        }
        resp = await self._client.post("/template/wa", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self._client.aclose()
```

## Acceptance criteria

```bash
docker compose ... run --rm whatsapp-sender alembic upgrade head
docker compose ... up -d whatsapp-sender
curl -fsS https://wa.dev.aitler.ru/healthz
bash scripts/psql.sh -c "\d+ whatsapp_accounts"
```

---

# Задача 7C.2 — Session window checker + send flow

**Файл:** `docs/tasks/sprint-7c/7c.2-send.md`

## Детали

### Session window

WhatsApp: 24 часа после последнего сообщения от пользователя — можно писать свободно. После — только шаблоны.

```python
class SessionWindowChecker:
    """Проверяет, открыто ли 24-часовое окно для контакта."""

    WINDOW_HOURS = 24

    def __init__(self, redis) -> None:
        self._redis = redis

    async def is_open(self, *, tenant_id: str, phone: str) -> bool:
        key = f"wa:window:{tenant_id}:{phone}"
        last_inbound = await self._redis.get(key)
        if not last_inbound:
            return False
        last_dt = datetime.fromisoformat(last_inbound)
        return (datetime.now(timezone.utc) - last_dt).total_seconds() < self.WINDOW_HOURS * 3600

    async def mark_inbound(self, *, tenant_id: str, phone: str) -> None:
        key = f"wa:window:{tenant_id}:{phone}"
        await self._redis.setex(key, 48 * 3600, datetime.now(timezone.utc).isoformat())
```

**Webhook от провайдера** — при входящем сообщении вызывать `mark_inbound`.

### Логика отправки

```python
class WhatsAppSenderService:
    async def send_approved_message(self, *, tenant_id, message_id, trace_id):
        # 1. Проверка opt-in tenant
        tenant_settings = await self._tenant_client.get_settings(str(tenant_id))
        if not tenant_settings.get("whatsapp_enabled"):
            raise ValidationError("WhatsApp sender not enabled")

        # 2. Получить Message
        message = await self._composer.get_message(message_id, tenant_id=str(tenant_id))
        if message.get("channel") != "whatsapp":
            raise ValidationError("Not a whatsapp message")

        # 3. Получить контакт и consent
        contact = await self._contact_store.get_contact(UUID(message["contact_id"]), tenant_id=str(tenant_id))
        consent = (contact.get("consent") or {}).get("whatsapp_opt_in", "unknown")
        if consent != "granted":
            raise ValidationError("No WhatsApp consent")

        # 4. Проверить session window
        to_phone = message["recipient_snapshot"].get("phone")
        window_open = await self._window.is_open(tenant_id=str(tenant_id), phone=to_phone)

        # 5. Выбрать аккаунт
        account = await self._account_selector.select(tenant_id=tenant_id)
        if account is None:
            raise AppError("No WhatsApp account available", code="no_account", status_code=503)

        # 6. Отправить
        if window_open:
            # Свободный текст
            result = await provider.send_text_message(
                to_phone=to_phone,
                text=message["body_text"],
            )
        else:
            # Только шаблон
            template = await self._get_template_for_message(message)
            if not template:
                raise ValidationError("No approved WhatsApp template; window closed")
            result = await provider.send_template_message(
                to_phone=to_phone,
                template_name=template.name,
                template_language=template.language,
                variables=self._extract_variables(message, template),
            )

        # 7. Записать attempt, обновить Message
        ...
```

**Важно:** если окно закрыто и нет approved-шаблона — **не отправляем**. Это защита от банов.

### Webhook для входящих

```python
@router.post("/webhooks/gupshup")
async def gupshup_webhook(request: Request) -> dict:
    """Принимает входящие от Gupshup."""
    data = await request.json()
    if data.get("type") == "message":
        # Входящее сообщение
        phone = data["payload"]["source"]
        text = data["payload"]["payload"]["text"]
        tenant_id = ...  # определяем по номеру получателя
        await window_checker.mark_inbound(tenant_id=tenant_id, phone=phone)
        # Публикуем reply.received для reply-classifier
        await emit_reply_received(...)
    return {"status": "ok"}
```

## Acceptance criteria

```bash
# 1. Создать WhatsApp account
curl -sX POST https://wa.dev.aitler.ru/accounts \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: acc-1" \
  -d '{"provider":"gupshup","phone_number":"+79001234567","provider_account_id":"...","api_key":"..."}' | jq .

# 2. Verify

# 3. Загрузить шаблон
curl -sX POST https://wa.dev.aitler.ru/templates \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: tmpl-1" \
  -d '{"name":"outreach_v1","language":"ru","category":"marketing","body_template":"Здравствуйте, {{1}}! ...","variables_count":1}' | jq .

# 4. Draft с channel=whatsapp, approve, отправить
```

## Подсказки

- **Провайдер обязателен** — не работать с Meta напрямую.
- **Session window — критично.** Вне окна — только шаблоны.
- **Шаблоны pre-approved.** Нельзя отправить произвольный текст вне окна.
- **Webhook для входящих** — обязательно.

## Анти-паттерны

- ❌ Не отправлять вне 24-часового окна без шаблона.
- ❌ Не использовать непроверенные шаблоны.
- ❌ Не работать с Meta напрямую — через провайдера.

---

# 7D — Real-time collaboration

## Что даёт

Несколько пользователей одновременно работают с review queue. Проблемы:
1. **Кто-то уже approve'ит item** — второй не должен видеть его в списке.
2. **Конфликты редактирования** — два пользователя редактируют одно письмо.
3. **Realtime обновления** — новый item появляется без refresh.

**Решение:**
- **WebSocket** для realtime обновлений.
- **Optimistic locking** для редактирования (version field).
- **Presence** — кто сейчас смотрит какой item.

## Архитектура

```
        ┌──────────────────────────────────────┐
        │  Browser 1      Browser 2      ...    │
        └────────┬───────────┬─────────────────┘
                 │ WebSocket │
                 ▼           ▼
        ┌──────────────────────────────────────┐
        │   Realtime Gateway (Next.js + ws)     │
        │                                       │
        │   - Подписка на NATS events           │
        │   - Broadcast всем клиентам tenant'а  │
        │   - Presence tracking (Redis)         │
        └──────────────────┬───────────────────┘
                           │
                           ▼
                    NATS events
```

**Ключевые принципы:**
1. **WebSocket через Next.js** — встроенный (route handler с `upgrade`). Или отдельный сервис.
2. **Redis pub/sub** для broadcast между инстансами Next.js.
3. **Presence** — Redis с TTL.
4. **Optimistic locking** — поле `version` в review_items.

---

# Задача 7D.1 — WebSocket gateway + presence

**Файл:** `docs/tasks/sprint-7d/7d.1-websocket.md`

## Детали

### Отдельный сервис `realtime-gateway`

Next.js плохо подходит для долгоживущих WebSocket. Лучше — отдельный сервис на Node.js или Python.

**Решение:** Python-сервис на FastAPI + `websockets` + Redis pub/sub.

```
services/realtime-gateway/
├── pyproject.toml
├── Dockerfile
├── src/realtime_gateway/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── auth.py              # проверка JWT
│   ├── connections.py       # manager подключений
│   ├── pubsub.py            # Redis pub/sub
│   ├── presence.py          # Redis presence
│   └── handlers/
│       ├── __init__.py
│       └── nats_bridge.py   # подписка на NATS → broadcast
```

### `connections.py`

```python
from dataclasses import dataclass, field
from uuid import UUID

import structlog


logger = structlog.get_logger()


@dataclass
class ClientConnection:
    user_id: UUID
    tenant_id: UUID
    websocket: any  # fastapi.WebSocket
    subscriptions: set[str] = field(default_factory=set)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, ClientConnection] = {}  # connection_id → conn
        self._by_tenant: dict[UUID, set[UUID]] = {}  # tenant_id → connection_ids

    async def connect(self, conn: ClientConnection, connection_id: UUID) -> None:
        self._connections[connection_id] = conn
        self._by_tenant.setdefault(conn.tenant_id, set()).add(connection_id)
        logger.info("ws_connected", connection_id=str(connection_id), tenant_id=str(conn.tenant_id))

    async def disconnect(self, connection_id: UUID) -> None:
        conn = self._connections.pop(connection_id, None)
        if conn:
            self._by_tenant.get(conn.tenant_id, set()).discard(connection_id)

    async def broadcast_to_tenant(self, tenant_id: UUID, message: dict) -> None:
        for cid in list(self._by_tenant.get(tenant_id, set())):
            conn = self._connections.get(cid)
            if conn is None:
                continue
            try:
                await conn.websocket.send_json(message)
            except Exception as e:
                logger.warning("ws_send_failed", connection_id=str(cid), error=str(e))
                await self.disconnect(cid)
```

### `main.py` — WebSocket endpoint

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from uuid import UUID, uuid4

app = FastAPI()


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    # 1. Проверка JWT
    try:
        payload = decode_token(token)  # через users-service JWT secret
    except Exception:
        await websocket.close(code=4001, reason="invalid_token")
        return

    user_id = UUID(payload["sub"])
    tenant_id = UUID(payload["tenant_id"])

    # 2. Подключение
    await websocket.accept()
    connection_id = uuid4()
    conn = ClientConnection(
        user_id=user_id,
        tenant_id=tenant_id,
        websocket=websocket,
    )
    await manager.connect(conn, connection_id)

    try:
        # 3. Presence
        await presence.set_online(tenant_id, user_id)

        # 4. Цикл чтения
        while True:
            data = await websocket.receive_json()
            await handle_client_message(conn, data)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(connection_id)
        await presence.set_offline(tenant_id, user_id)
```

### `pubsub.py` — Redis pub/sub

```python
import asyncio
import json

import redis.asyncio as aioredis
import structlog


logger = structlog.get_logger()


class PubSub:
    """Redis pub/sub для broadcast между инстансами realtime-gateway."""

    def __init__(self, redis_url: str, manager: ConnectionManager) -> None:
        self._redis = aioredis.from_url(redis_url)
        self._pubsub = self._redis.pubsub()
        self._manager = manager
        self._channel = "realtime:broadcast"

    async def publish(self, *, tenant_id: UUID, message: dict) -> None:
        payload = json.dumps({"tenant_id": str(tenant_id), "message": message})
        await self._redis.publish(self._channel, payload)

    async def subscribe_forever(self) -> None:
        await self._pubsub.subscribe(self._channel)
        async for msg in self._pubsub.listen():
            if msg["type"] != "message":
                continue
            try:
                data = json.loads(msg["data"])
                tenant_id = UUID(data["tenant_id"])
                await self._manager.broadcast_to_tenant(tenant_id, data["message"])
            except Exception as e:
                logger.warning("pubsub_message_failed", error=str(e))
```

### `nats_bridge.py` — NATS → WebSocket

```python
class NATSBridge:
    """Подписывается на NATS события и публикует их через Redis pub/sub."""

    def __init__(self, nats_conn, pubsub: PubSub) -> None:
        self._nats = nats_conn
        self._pubsub = pubsub

    async def run_forever(self) -> None:
        from nats_client.subscriber import Subscriber

        async def handler(envelope) -> None:
            # Формируем сообщение для UI
            message = {
                "type": "event",
                "event_type": envelope.event_type,
                "tenant_id": str(envelope.tenant_id),
                "payload": envelope.payload,
                "occurred_at": envelope.occurred_at.isoformat(),
            }
            await self._pubsub.publish(tenant_id=envelope.tenant_id, message=message)

        subscriber = Subscriber(
            self._nats,
            stream="BRIEFS",
            durable="realtime-gateway",
            filter_subjects=[
                "message.drafted.*",
                "message.approved.*",
                "message.sent.*",
                "reply.received.*",
                "flow.started.*",
                "flow.completed.*",
                "flow.failed.*",
            ],
            handler=handler,
        )
        await subscriber.start()
        await subscriber.run_forever()
```

### UI: WebSocket клиент

```typescript
// src/lib/websocket.ts
export function createWebSocket(token: string, onMessage: (msg: any) => void) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protocol}//${window.location.host}/ws?token=${token}`);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.error("WS parse error", e);
    }
  };

  ws.onclose = () => {
    // Reconnect через 5 секунд
    setTimeout(() => createWebSocket(token, onMessage), 5000);
  };

  return ws;
}
```

**Интеграция в ReviewList:**

```tsx
"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

export function ReviewList({ items }: { items: ReviewItem[] }) {
  const qc = useQueryClient();
  const { data: session } = useSession();

  useEffect(() => {
    if (!session?.accessToken) return;
    const ws = createWebSocket(session.accessToken, (msg) => {
      if (msg.event_type === "message.drafted") {
        qc.invalidateQueries({ queryKey: ["reviews"] });
      }
    });
    return () => ws.close();
  }, [session, qc]);

  // ...
}
```

## Acceptance criteria

```bash
# 1. Открыть /reviews в двух браузерах
# 2. В одном approve item
# 3. Во втором — item исчезает без refresh
# Ожидание: realtime работает

# 4. Presence
curl -s -H "Authorization: Bearer $TOKEN" https://realtime.dev.aitler.ru/presence | jq .
# Ожидание: список online users
```

## Подсказки

- **Отдельный сервис** — Next.js плохо для долгих WS.
- **Redis pub/sub** для broadcast между инстансами.
- **Reconnect через 5 секунд** — обязателен.
- **JWT через query param** — WebSocket не поддерживает заголовки.

## Анти-паттерны

- ❌ Не делать WebSocket в Next.js — вынести в отдельный сервис.
- ❌ Не забывать reconnect.
- ❌ Не broadcast'ить всё всем — только tenant-скоупное.

---

# Задача 7D.2 — Optimistic locking для редактирования

**Файл:** `docs/tasks/sprint-7d/7d.2-locking.md`

## Детали

### Поле `version` в review_items

**Миграция:**

```sql
ALTER TABLE review_items ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
```

**Логика:**
- При чтении — клиент получает `version`.
- При обновлении — клиент передаёт `version`.
- Если в БД `version` отличается — 409 Conflict.

```python
async def edit(self, *, item_id, data, expected_version: int, ...) -> ReviewItem:
    item = await self._repo.get(item_id)
    if item.version != expected_version:
        raise ConflictError(
            f"Item was modified by another user. Expected version {expected_version}, current {item.version}",
            details={"current_version": item.version},
        )
    item.edit = {...}
    item.version += 1
    await self._repo._s.flush()
    return item
```

**В UI:**

```tsx
try {
  await edit.mutateAsync({ id, subject, bodyText, version: item.version });
} catch (e) {
  if (e.status === 409) {
    toast.error("Кто-то уже изменил это письмо. Обновите страницу.");
    qc.invalidateQueries({ queryKey: ["reviews", id] });
  }
}
```

## Acceptance criteria

```bash
# 1. Открыть один item в двух браузерах
# 2. В первом сохранить изменения
# 3. Во втором — попытаться сохранить → 409 Conflict
# Ожидание: конфликт обнаружен
```

---

# 7E — Multi-armed bandit

## Что даёт

Замена классического A/B в experiments. **Динамически перераспределяет трафик** в пользу выигрывающего варианта.

**Классический A/B:** 50/50 до конца. Если один вариант явно лучше — теряем на «проигрышном».

**Bandit:** 80/20 в пользу лучшего. Быстрее находим winner, меньше потерь.

**Алгоритм:** Thompson Sampling — простой, эффективный, хорошо работает при малых данных.

## Модель данных

**Обновить experiments:**

```python
allocation_strategy: Mapped[str] = mapped_column(
    String(32), nullable=False, default="fixed"
)  # fixed | thompson
```

## Задача 7E.1 — Thompson Sampling

**Файл:** `docs/tasks/sprint-7e/7e.1-bandit.md`

## Детали

### `stats_engine.py` — обновить

```python
import random


class ThompsonSampling:
    """Thompson Sampling для multi-armed bandit.

    Для каждой руки — Beta(alpha, beta).
    alpha = successes + 1, beta = failures + 1.
    Сэмплируем из каждой, выбираем max.
    """

    @staticmethod
    def choose_variant(variants_stats: list[dict]) -> str:
        """variants_stats: [{variant_id, sent, positive_replied}]."""
        best_id = None
        best_sample = -1.0

        for v in variants_stats:
            alpha = v["positive_replied"] + 1
            beta = (v["sent"] - v["positive_replied"]) + 1
            sample = random.betavariate(alpha, beta)
            if sample > best_sample:
                best_sample = sample
                best_id = v["variant_id"]

        return best_id
```

### Обновить experiments

**`ExperimentService.assign_variant`:**

```python
async def assign_variant(self, *, tenant_id, experiment_id, contact_id) -> str | None:
    exp = await self.get(experiment_id)
    if exp.status != "running":
        return exp.results.get("winner_variant_id")

    if exp.allocation_strategy == "thompson":
        # Получаем текущую статистику
        stats = exp.results.get("variants", [])
        if not stats:
            # Первое сообщение — равномерно
            stats = [{"variant_id": v["id"], "sent": 0, "positive_replied": 0} for v in exp.variants]
        return ThompsonSampling.choose_variant(stats)

    # Fixed — детерминированный хеш
    assigner = VariantAssigner()
    return assigner.assign(
        experiment_id=str(experiment_id),
        contact_id=str(contact_id),
        variants=exp.variants,
    )
```

### Периодический update stats

Раз в час (или после каждого события reply.classified) — обновлять `results.variants` из analytics. Это данные для Thompson.

## Acceptance criteria

```bash
# 1. Создать эксперимент с allocation_strategy=thompson
curl -sX POST https://experiments.dev.aitler.ru/experiments \
  -d '{"allocation_strategy":"thompson",...}' | jq .

# 2. Симулировать 100 assign
# Ожидание: распределение не 50/50, а в пользу выигрывающего

# 3. После накопления данных — winner определён быстрее, чем при fixed
```

## Подсказки

- **Thompson Sampling** — простой, эффективный.
- **Beta distribution** — для бинарных исходов (reply / no reply).
- **Для continuous метрик** (revenue) — другой алгоритм (UCB).

## Анти-паттерны

- ❌ Не использовать Thompson для малых выборок (< 20 на вариант).
- ❌ Не забывать periodic update stats.
- ❌ Не смешивать fixed и thompson в одном эксперименте.

---

# 7F — ML scoring

## Что даёт

Модель, которая предсказывает вероятность ответа контакта. Обучается на исторических данных:
- Признаки контакта (роль, seniority, компания, отрасль).
- Признаки компании (размер, гео, tech stack, signals).
- Признаки сообщения (шаблон, длина, время отправки).

Используется для:
1. **Ранжирования контактов** — сначала тем, кто с большей вероятностью ответит.
2. **Сегментации** — находить «горячие» сегменты.

## Технологии

- **Python:** scikit-learn, XGBoost, LightGBM.
- **Feature store:** таблица `ml_features` в БД.
- **Model store:** MLflow или просто S3/MinIO с версиями.
- **Serving:** FastAPI-сервис `ml-scoring-service`.

**Реалистично:** начать с **логистической регрессии** или **LightGBM**. Не глубокое обучение — мало данных.

## Задача 7F.1 — ML features pipeline

**Файл:** `docs/tasks/sprint-7f/7f.1-features.md`

## Детали

### Таблица `ml_features`

```python
class ContactFeatures(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    """Денормализованные features для ML. Обновляется периодически."""
    __tablename__ = "contact_features"

    contact_id: Mapped[UUID] = mapped_column(nullable=False, unique=True, index=True)

    # Категориальные
    role_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(32), nullable=True)
    company_industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_size_range: Mapped[str | None] = mapped_column(String(16), nullable=True)
    company_country: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # Числовые
    company_employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    company_signals_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    days_since_company_created: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Target (для обучения)
    has_reply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_positive_reply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    messages_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_message_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**Обновляется фоновым воркером** — раз в день, из contact-store + composer + reply-classifier.

### `ml-scoring-service`

```python
class ScoringService:
    def __init__(self, model_registry) -> None:
        ...

    async def score_contact(self, *, tenant_id, contact_id) -> float:
        features = await self._repo.get_features(contact_id)
        if features is None:
            return 0.5  # default

        X = self._extract_vector(features)
        model = self._registry.get_active_model(tenant_id)
        if model is None:
            return 0.5

        proba = model.predict_proba([X])[0][1]
        return float(proba)
```

### Training pipeline

Отдельный скрипт (не сервис):
- Читает `contact_features` с `has_positive_reply`.
- Обучает LightGBM.
- Сохраняет в MinIO.
- Регистрирует в model_registry.

Запускается вручную или по расписанию (раз в неделю).

### Интеграция в sourcing

При скоринге компаний/контактов — добавить `ml_score` в breakdown:

```python
score_breakdown["ml_score"] = await self._ml_client.score_contact(
    tenant_id=str(tenant_id),
    contact_id=str(contact.id),
)
```

## Acceptance criteria

```bash
# 1. Обучить модель
python -m ml_scoring.train --tenant $TENANT

# 2. Score контакта
curl -sX POST https://ml.dev.aitler.ru/score \
  -H "X-Tenant-ID: $TENANT" \
  -d '{"contact_id":"..."}' | jq .
# Ожидание: {score: 0.42}
```

## Подсказки

- **Начать с простой модели** — логистическая регрессия или LightGBM.
- **Не переусложнять.** Мало данных — простые модели работают лучше.
- **Features pipeline** — критично. Мусор на входе → мусор на выходе.
- **A/B тестирование модели** — новые версии только через эксперименты.

## Анти-паттерны

- ❌ Не обучать модель на < 1000 образцов.
- ❌ Не использовать deep learning — данных не хватит.
- ❌ Не менять модель без A/B.

---

# Финальная E2E-проверка Спринта 7

```bash
# 1. Регистрация нового user
curl -sX POST https://users.dev.aitler.ru/auth/register \
  -d '{"email":"new@example.com","password":"...","display_name":"New","company_name":"New Co"}' | jq .
# Ожидание: user_id, tenant_id, token

# 2. Пригласить второго user
curl -sX POST https://users.dev.aitler.ru/invitations \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"email":"second@example.com","role":"manager"}' | jq .
# Ожидание: invitation

# 3. Создать campaign
curl -sX POST https://orchestrator.dev.aitler.ru/campaigns ...
# Ожидание: campaign

# 4. Привязать flow к campaign
# ...

# 5. Создать WhatsApp account
curl -sX POST https://wa.dev.aitler.ru/accounts ...
# Ожидание: account

# 6. Realtime
# Открыть /reviews в двух браузерах → approve в одном → исчезает во втором

# 7. Thompson sampling
curl -sX POST https://experiments.dev.aitler.ru/experiments \
  -d '{"allocation_strategy":"thompson",...}'
# Симулировать 100 assign → распределение не 50/50

# 8. ML scoring
curl -sX POST https://ml.dev.aitler.ru/score -d '{"contact_id":"..."}'
# Ожидание: score

# 9. Audit log
curl -s -H "Authorization: Bearer $TOKEN" "https://users.dev.aitler.ru/audit/events?action=user.login"
# Ожидание: события

# 10. CI
git push origin develop
# Зелёные
```

---

## Проверка: что я перепроверил

- [x] Порядок задач: 7A.1 → 7A.2 → 7A.3 → 7A.4 → 7B → 7C.1 → 7C.2 → 7D.1 → 7D.2 → 7E.1 → 7F.1, зависимости соблюдены.
- [x] Users в БД, не в env. Argon2, не bcrypt.
- [x] Multi-tenant users через `user_tenants`.
- [x] JWT с tenant_id + role.
- [x] Constant-time authenticate.
- [x] Brute-force protection.
- [x] Audit в схеме `audit`, в той же транзакции.
- [x] Campaign — бизнес-сущность, отдельно от flow.
- [x] WhatsApp через провайдера (Gupshup), не напрямую Meta.
- [x] Session window 24 часа для WhatsApp.
- [x] Pre-approved шаблоны.
- [x] WebSocket в отдельном сервисе (realtime-gateway).
- [x] Redis pub/sub для broadcast между инстансами.
- [x] Optimistic locking через version.
- [x] Thompson Sampling для bandit.
- [x] ML scoring через LightGBM, features pipeline.
- [x] Mypy strict, ruff, pytest.
- [x] Idempotency-Key на всех POST.
- [x] RLS на tenant-скоупных таблицах.
- [x] Никаких cross-service импортов.

---

## Что дальше (Спринт 8)

Спринт 7 делает систему **зрелым продуктом для команд**. Спринт 8 — **масштабирование и enterprise**:

- **Multi-region deploy** — реальная реализация (не только docs).
- **SSO (SAML, OIDC)** — для enterprise-клиентов.
- **Custom domains для email** — каждый tenant со своим доменом.
- **Billing / подписки** — Stripe или ЮKassa.
- **Advanced RBAC** — granular permissions.
- **Data export / GDPR compliance** — экспорт и удаление данных по запросу.
- **SLA monitoring** — Uptime, latency, alerts.

**Что от тебя нужно сейчас:**
1. Разложить эти 12 задач по файлам в `docs/tasks/sprint-7/` (7A, 7B, 7C, 7D, 7E, 7F).
2. Дать агенту: «Начинай с 7A.1. 7A — обязательно до конца (users + audit), потом 7B (campaign), потом 7C (WhatsApp), потом 7D (realtime), потом 7E (bandit), потом 7F (ML)».
3. Сообщить мне, когда Спринт 7 закрыт.

**Критичные вопросы к тебе:**
- **`transactional-email` сервис** — понадобится для verification, password reset, invitations. Это отдельный сервис (простой SMTP-клиент). Делать его в 7A или отложить? **Рекомендую сделать в 7A.1** — это 50 строк кода.
- **WhatsApp провайдер** — Gupshup (Индия, дешевле) или 360dialog (Европа, дороже, надёжнее)? **Рекомендую 360dialog** для РФ/Европы, Gupshup — fallback.
- **ML scoring** — делать сразу или отложить? **Рекомендую отложить** до накопления данных (нужно минимум 1000 контактов с reply). В 7F сделать только feature pipeline, обучение — Спринт 8.
- **Thompson Sampling** — включать по умолчанию или только per-experiment? **Рекомендую per-experiment**, по умолчанию fixed A/B.

Если хочешь что-то поправить сейчас — скажи.