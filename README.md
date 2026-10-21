# ozon-seller-mcp

MCP-сервер для [Ozon Seller API](https://docs.ozon.ru/api/seller/) — позволяет AI-ассистентам (Claude, AGY, Cursor и др.) работать с вашим магазином на Ozon.

## Что изменено по сравнению с исходным репозиторием

В исходной версии репозитория многие эндпоинты устарели (были отключены Ozon в 2025–2026 гг.) либо содержали несовместимые схемы запросов. Проведен полный аудит и адаптация всех методов под актуальный API:

1. **Склады (Warehouses):**
   - `warehouse_list`: обновлен с отключенного `/v1/warehouse/list` (HTTP 400 code 9) на актуальный `/v2/warehouse/list`.
   - `warehouse_fbo_list`: исправлены обязательные параметры Ozon API (`search` мин. 4 символа, `filter_by_supply_type`).

2. **Категории (Categories & Attributes):**
   - Полный переезд с удаленных эндпоинтов `/v1/category/...` (HTTP 404) на модель описательных категорий `/v1/description-category/...`:
     - `category_tree` → `/v1/description-category/tree`
     - `category_attributes` → `/v1/description-category/attribute` (`description_category_id`, `type_id`)
     - `category_attribute_values` → `/v1/description-category/attribute/values` (`attribute_id`, справочники значений)

3. **Товары (Products):**
   - `product_list`: исправлена валидация — параметр `visibility` теперь передается внутри обязательного объекта `filter`.
   - `product_info`: переведен на `/v3/product/info/list` взамен удаленного `/v2/product/info` (HTTP 404).
   - `product_info_list`: добавлена валидация и поддержка поиска по `sku`.
   - `product_info_attributes`, `prices_info`, `stocks_info`: гарантирована передача обязательного блока `filter`.
   - `product_delete`: исправлена схема тела запроса — теперь передается `{"products": [{"offer_id": ...}]}` вместо `product_id`.

4. **Остатки (Stocks):**
   - `stocks_by_warehouse_fbs`: переведен с устаревшего `/v1` на `/v2/product/info/stocks-by-warehouse/fbs` с обязательным параметром `limit`.

5. **Заказы FBS (FBS Orders):**
   - `fbs_ship`: обновлен с нерабочего `/v2/posting/fbs/ship` (HTTP 404) на актуальный `/v4/posting/fbs/ship`.
   - `fbs_set_tracking_number`: исправлен путь на `/v2/fbs/posting/tracking-number/set` и формат списка `tracking_numbers`.
   - `fbs_cancel_reasons`: обновлен на метод справочника `/v2/posting/fbs/cancel-reason/list`.
   - `fbs_unfulfilled_list`: добавлены значения по умолчанию для диапазона дат `cutoff_from` / `cutoff_to` для предотвращения ошибки `the mismatch between cutoff & delivery date`.
   - `fbs_posting_list`: добавлена автоматическая подстановка диапазона дат по умолчанию.
   - `fbs_act_create`: даты автоматически приводятся к формату RFC3339.

6. **Финансы (Finance):**
   - Метод `/v3/finance/transaction/list` был отключен Ozon 6 июля 2026 г. Добавлены новые актуальные инструменты:
     - `finance_accrual_by_day` (`/v1/finance/accrual/by-day`) — ежедневные начисления и детализация комиссий.
     - `finance_decompensation` (`/v1/finance/decompensation`) — отчет об удержаниях (штрафы, акции, реклама).
     - `finance_compensation` (`/v1/finance/compensation`) — отчет о компенсациях продавцу.
     - `finance_transactions` адаптирован для вызова начислений за день.
   - `finance_realization`: исправлена передача параметров с `"date": "YYYY-MM"` на целочисленные `year` и `month` (`/v2/finance/realization`).

7. **Отчеты о возвратах (Returns):**
   - `returns_report_create`: скорректирована схема для `/v2/report/returns/create` (обязательные даты в RFC3339 и числовой статус enum).

8. **Чаты (Chats):**
   - Переведены с удаленной v1 на v3/v2: `chat_list` (`/v3/chat/list`), `chat_history` (`/v3/chat/history`), `chat_mark_read` (`/v2/chat/read`). Добавлена документация о необходимости тарифа Premium Plus.

9. **Отзывы и рейтинг (Reviews & Ratings):**
   - `review_list`: ограничение `limit` теперь автоматически клампится в допустимый Ozon диапазон `[20, 100]`.
   - `rating_history`: авто-конвертация дат в RFC3339 и предустановленный список ключевых метрик по умолчанию.

10. **Инфраструктура:**
    - Реализована автоматическая загрузка файла `.env` при локальном запуске или через скрипты без явных переменных окружения.
    - Добавлен хелпер нормализации дат `_to_rfc3339` (поддерживает как `YYYY-MM-DD`, так и полные ISO/RFC3339 строки).
    - Добавлен хелпер нормализации денежных значений `_normalize_money` в формат Ozon Money (`{"amount": "...", "currency": "RUB"}`).

11. **Акции и автодобавление (Promotions & Auto-add):**
    - `promotion_products_update` (`/v1/actions/products/update`) — универсальный метод добавления/обновления/удаления товаров в акциях на основе предельной цены `action_price` (заменяет устаревший `/v1/actions/products/activate`).
    - `promotion_activate` — перенаправлен на современный эндпоинт `/v1/actions/products/update`.
    - `auto_add_products_list` (`/v2/actions/auto-add/products/list`) — получение списка товаров из автодобавления в акцию.
    - `auto_add_products_candidates` (`/v2/actions/auto-add/products/candidates`) — получение списка кандидатов для автодобавления.
    - `auto_add_products_delete` (`/v2/actions/auto-add/products/delete`) — удаление товаров из автодобавления в акцию.
    - `auto_add_products_update` (`/v2/actions/auto-add/products/update`) — добавление/обновление товаров в автодобавлении в акцию.

## Возможности

- **Товары** — просмотр (`product_list`, `product_info`, `product_info_list`), создание, обновление, архивация, удаление, характеристики, загрузка изображений
- **Цены** — получение и обновление цен (`prices_info`, `prices_update`)
- **Остатки** — просмотр и обновление остатков (`stocks_info`, `stocks_update`, `stocks_by_warehouse_fbs` v2)
- **Заказы FBS** — список, несобранные заказы, детали, сборка/отправка (`fbs_ship` v4), отмена, этикетки, трекинг (`fbs_set_tracking_number` v2)
- **Заказы FBO** — список и детали
- **Склады** — список складов продавца (`warehouse_list` v2) и складов FBO для поставок (`warehouse_fbo_list`)
- **Категории** — дерево описательных категорий и типов (`category_tree`), атрибуты и справочники значений (`category_attributes`, `category_attribute_values`)
- **Аналитика** — продажи, просмотры, конверсии (`analytics_data`), остатки на складах (`analytics_stocks`)
- **Финансы** — ежедневные начисления (`finance_accrual_by_day`), удержания (`finance_decompensation`), компенсации (`finance_compensation`), реализация (`finance_realization`)
- **Отчеты о возвратах** — создание отчетов (`returns_report_create` v2)
- **Чаты** — переписка с покупателями (v3 API, для тарифа Premium Plus)
- **Отзывы** — просмотр и ответы на отзывы
- **Рейтинг** — текущий рейтинг продавца и история по метрикам
- **Акции** — список акций (`promotions_list`), кандидаты (`promotion_candidates`), товары в акции (`promotion_products`), управление товарами (`promotion_products_update`, `promotion_activate`, `promotion_deactivate`), а также автодобавление v2 (`auto_add_products_list`, `auto_add_products_candidates`, `auto_add_products_delete`, `auto_add_products_update`)

## Установка

```bash
# Клонировать репозиторий
git clone https://github.com/madex1/ozon-seller-mcp.git
cd ozon-seller-mcp

# Установить зависимости
uv sync
```

## Настройка

Получите Client ID и API Key в личном кабинете Ozon Seller → Настройки → Seller API.

```bash
cp .env.example .env
# Заполните OZON_CLIENT_ID и OZON_API_KEY
```

## Использование с Claude Desktop

Добавьте в `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ozon-seller": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ozon-seller-mcp", "python", "server.py"],
      "env": {
        "OZON_CLIENT_ID": "your_client_id",
        "OZON_API_KEY": "your_api_key"
      }
    }
  }
}
```

## Использование с Claude Code

Добавьте в `.claude/settings.json`:

```json
{
  "mcpServers": {
    "ozon-seller": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ozon-seller-mcp", "python", "server.py"],
      "env": {
        "OZON_CLIENT_ID": "your_client_id",
        "OZON_API_KEY": "your_api_key"
      }
    }
  }
}
```

## Лицензия

MIT
