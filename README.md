# Telegram Anonymous Messaging & Channel Publishing Platform

A production-ready, modular, and secure Telegram anonymous communication platform built with **Python 3.12+**, **Aiogram 3.x**, **PostgreSQL**, **SQLAlchemy 2.x (async)**, **Alembic**, and **Redis**.

The platform provides two strictly separated communication modes:
1. **Persistent 1-to-1 Personal Anonymous Conversations** via personal deep links (`p_*`).
2. **Anonymous Publishing to Telegram Channels** via dedicated channel submission links (`c_*`).

---

## 1. System Architecture

```
                 +-----------------------------------+
                 |        Telegram Bot API           |
                 +-----------------+-----------------+
                                   |
                                   v
    +-----------------------------------------------------------------+
    |                     Aiogram 3 Dispatcher                        |
    |  - DatabaseMiddleware (Async SQLAlchemy Session + User Sync)    |
    |  - RateLimitMiddleware (Redis sliding-window rate limiter)      |
    +------------------------------+----------------------------------+
                                   |
          +------------------------+------------------------+
          |                                                 |
          v                                                 v
+-------------------------------+         +----------------------------------+
|   Personal Anonymous Chat     |         |   Anonymous Channel Publishing   |
|-------------------------------|         |----------------------------------|
| • Deep link: p_{token|slug}   |         | • Deep link: c_{token|slug}      |
| • Multi-conversation inbox    |         | • Content reconstruction         |
| • Message-level reply routing |         | • Template engine                |
| • Conversation block & report |         | • Seen button (Idempotent)       |
+---------------+---------------+         +-----------------+----------------+
                |                                           |
                +---------------------+---------------------+
                                      |
                                      v
    +-----------------------------------------------------------------+
    |                     Domain Services Layer                       |
    | • LinkService (Tokens, slugs, strict prefix validation)         |
    | • AnonymousChatService (Reconstructs media & dispatches)       |
    | • ChannelPublishingService (Renders templates & publishes)      |
    | • SeenService (Tracks explicit seen events & milestones)        |
    | • ContentFilterService & RateLimitService                       |
    +---------------------------------+-------------------------------+
                                      |
                 +--------------------+--------------------+
                 v                                         v
+-----------------------------------+   +------------------------------------+
|       PostgreSQL Database         |   |            Redis Pool              |
|  - Users, Links, Conversations    |   |  - FSM Storage                     |
|  - Messages, Blocks, Reports      |   |  - Active Reply Targets (TTL)      |
|  - Channels, Admins, Seen Events  |   |  - Rate Limits & Deduplication     |
+-----------------------------------+   +------------------------------------+
```

---

## 2. Key Features

- **Strict Namespace Isolation:** `p_` links are strictly mapped to personal inboxes, and `c_` links are mapped to channels. Cross-namespace transformation is blocked.
- **High-Entropy Opaque Tokens:** Tokens are generated using Python's `secrets` module (`secrets.token_urlsafe`), preventing predictability and user enumeration.
- **Message-Level Reply Targeting:** Owners can have hundreds of simultaneous conversations. Clicking `[↩️ Reply]` sets the specific target message in Redis (`reply_target:{owner_tg_id}`), ensuring responses never leak across conversations.
- **Media Reconstruction:** Content (text, photo, voice, video, document, audio, animation, stickers) is reconstructed cleanly without Telegram forward tags or metadata.
- **Explicit Seen Button:** Idempotent viewing tracker attached to channel posts with milestone notifications to the author.
- **Persian UI & Localization:** Localized Persian UX with extensible dictionary system in `app/config/messages.py`.

---

## 3. Deployment & Quickstart

### Prerequisites
- Linux VPS (Ubuntu 22.04+ or Debian 12+)
- Docker & Docker Compose
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Step 1: Clone and Configure Environment
```bash
cp .env.example .env
nano .env
```
Ensure you provide:
- `BOT_TOKEN`: Token obtained from @BotFather.
- `BOT_USERNAME`: Username of the bot without `@`.
- `ADMIN_IDS`: Comma-separated Telegram User IDs of system admins.
- `SECRET_KEY`: A secure random 32-character string.

### Step 2: Launch with Docker Compose
```bash
docker compose up -d --build
```

### Step 3: Run Database Migrations
Migrations are applied automatically or manually via Alembic:
```bash
docker compose exec bot alembic upgrade head
```

---

## 4. Operational Workflows

### Connecting a Channel
1. Add the bot as an **Administrator** with *Post Messages* permission to your Telegram channel.
2. In the bot, navigate to `📢 کانال‌های متصل` -> `➕ راهنمای اتصال کانال جدید`.
3. The channel submission link `https://t.me/BOT_USERNAME?start=c_<token>` is generated.

### Managing Personal Links
1. Open `🔗 لینک ناشناس من`.
2. Users can:
   - Temporarily disable/enable their link.
   - Regenerate the opaque random token.
   - Choose a unique custom slug (e.g., `p_shadow`).

---

## 5. Automated Testing

Run the comprehensive test suite with:
```bash
PYTHONPATH=. pytest -v
```

Tests cover:
- Cryptographic token unpredictability and slug validation.
- Personal vs channel namespace separation.
- Message-level reply targeting and multi-conversation isolation (Owner replying to Alice, Bob, Charlie).
- Block and abuse reporting mechanisms.
- Channel publication and template variable validation.
- Explicit Seen button idempotency and milestone notifications.
- Redis-backed rate limiting and duplicate detection.

---

## 6. Telegram API Limitations & Architectural Solutions

1. **Passive Channel Views:** Telegram Bot API does NOT notify bots when a subscriber views a post.
   - *Solution:* Implemented explicit `[👁 پیام را دیدم]` button with unique user idempotency.
2. **Sender Attribution on Forwards:** Native forwards expose sender IDs.
   - *Solution:* Content is reconstructed and posted directly by the bot, stripping attribution.
3. **Channel Discussion Permissions:** Discussion groups are linked natively by Telegram; comments inside discussion groups rely on Telegram's native comment threading.
