# Async Payment Processing Service

Тестовый микросервис асинхронной обработки платежей на FastAPI, PostgreSQL, SQLAlchemy 2.0 async, RabbitMQ/FastStream и Alembic.

## Архитектура

Путь запроса:

1. `POST /api/v1/payments` проверяет `X-API-Key` и `Idempotency-Key`.
2. В **одной транзакции PostgreSQL** создаются `payments` и запись `outbox`.
3. Outbox worker читает неопубликованные события с `FOR UPDATE SKIP LOCKED`, публикует их в durable очередь `payments.new` и только после подтверждённой публикации отмечает событие опубликованным.
4. Consumer получает `payment_id`, блокирует платеж, эмулирует gateway 2–5 секунд, выставляет `succeeded` с вероятностью 90% или `failed` с вероятностью 10%, сохраняет `processed_at`.
5. Consumer отправляет webhook. При сетевой ошибке или HTTP 4xx/5xx выполняется до 3 попыток с exponential backoff: 1s, 2s.
6. После третьей неудачной попытки webhook-событие отправляется в durable `payments.dlq`.

Outbox даёт at-least-once доставку: если publisher успел отправить сообщение, но упал до фиксации `published`, событие может прийти повторно. Consumer идемпотентен: платеж со статусом, отличным от `pending`, повторно не процессится.

## Запуск

```bash
cp .env.example .env
docker compose up --build
```

После старта:

- API / Swagger: `http://localhost:8000/docs`
- RabbitMQ Management: `http://localhost:15672` (`guest` / `guest`)

По умолчанию API key: `change-me`. Для реального окружения поменяйте `API_KEY` в `.env`.

## Создание платежа

```bash
curl -i -X POST http://localhost:8000/api/v1/payments \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: change-me' \
  -H 'Idempotency-Key: order-1001' \
  -d '{
    "amount": "1500.00",
    "currency": "RUB",
    "description": "Order #1001",
    "metadata": {"order_id": 1001},
    "webhook_url": "https://webhook.site/your-id"
  }'
```

Ответ: `202 Accepted`:

```json
{
  "payment_id": "...",
  "status": "pending",
  "created_at": "..."
}
```

Повторный POST с тем же `Idempotency-Key` вернёт тот же платеж и не создаст новую outbox-запись.

## Получение платежа

```bash
curl http://localhost:8000/api/v1/payments/<payment_id> \
  -H 'X-API-Key: change-me'
```

## Webhook payload

```json
{
  "payment_id": "...",
  "status": "succeeded",
  "processed_at": "..."
}
```

## Миграции

При `docker compose up` сервис `migrate` автоматически выполняет:

```bash
alembic upgrade head
```

Создание новой миграции локально:

```bash
docker compose run --rm api alembic revision --autogenerate -m "change"
```

## Тесты

```bash
docker compose run --rm api pytest -q
```

## Основные решения

- `Decimal/Numeric(18,2)` вместо float для денег.
- Unique constraint на `idempotency_key` защищает от гонок двух одинаковых запросов.
- Payment + Outbox создаются атомарно в одной DB-транзакции.
- `FOR UPDATE SKIP LOCKED` позволяет безопасно масштабировать outbox workers.
- Durable RabbitMQ queues + persistent messages уменьшают риск потери событий при рестарте брокера.
- Consumer проверяет текущий статус платежа, поэтому повторная доставка не приводит к повторному процессингу.
- Webhook retry ограничен тремя попытками; после исчерпания попыток сообщение попадает в DLQ для ручного разбора/повторной обработки.

## Структура

```text
app/
  api/          FastAPI endpoints
  core/         config, API-key auth
  db/           async SQLAlchemy engine/session
  models/       Payment, Outbox
  schemas/      Pydantic v2 schemas
  services/     payment business logic
  workers/      FastStream consumer + Outbox publisher
alembic/        migrations
tests/          tests
```

## Надёжность и семантика доставки

- `POST /api/v1/payments` сохраняет `payments` и `outbox` в одной транзакции. Поэтому событие не теряется между коммитом платежа и публикацией в RabbitMQ.
- Outbox publisher выбирает строки через `FOR UPDATE SKIP LOCKED`, поэтому можно безопасно запускать несколько publisher-процессов.
- `idempotency_key` защищён уникальным ограничением PostgreSQL. Предварительная проверка ускоряет обычный случай, а обработка `IntegrityError` закрывает race condition при двух одновременных запросах.
- Consumer идемпотентен относительно повторной доставки события: платёж обрабатывается только в статусе `pending`.
- Webhook выполняется максимум 3 раза с exponential backoff 1s → 2s. После третьей ошибки уведомление публикуется в `payments.dlq` через отдельный dead-letter exchange `payments.dlx`, чтобы его можно было диагностировать и переиграть отдельно от самого платежа.

### Что именно гарантирует Outbox

Outbox даёт at-least-once публикацию. Возможна ситуация, когда сообщение успешно попало в RabbitMQ, но publisher упал до отметки `published` в PostgreSQL. Тогда событие будет опубликовано повторно. Поэтому consumer обязан быть идемпотентным — это ожидаемая часть Outbox pattern, а не ошибка реализации.
