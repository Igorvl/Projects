# Gemini API: Tiers, Quotas & Key Rotation

> **Контекст:** Диагностика проблемы "6 ключей Gemini Pro → всё равно 429" в Project DNA.
> Дата: 2026-04-01

---

## 1. Главное открытие: квоты по Project, а не по API Key

Официальная документация Google:
> **"Rate limits are applied per project, not per API key."**
> — https://ai.google.dev/gemini-api/docs/rate-limits

```
GCP Project "my-gemini-app"
    ├── GEMINI_API_KEY   (ключ 1)  ─┐
    ├── GEMINI_API_KEY_2 (ключ 2)  ─┤── Один общий бакет квоты на ПРОЕКТ
    └── GEMINI_API_KEY_3 (ключ 3)  ─┘

GCP Project "my-gemini-app-2" (другой Google-аккаунт!)
    └── GEMINI_API_KEY_4            ──── Отдельный бакет квоты ✅
```

**Следствие:** Ротация ключей из ОДНОГО проекта не помогает при исчерпании
дневного лимита. Нужны ключи из РАЗНЫХ GCP Projects (= разных Google-аккаунтов).

---

## 2. Google One Pro ≠ Gemini API Paid Tier

Это два абсолютно разных продукта:

| | Google One Pro | Gemini API Paid Tier |
|---|---|---|
| **Что это** | Потребительская подписка | Разработческий API tier |
| **Где активируется** | Настройки аккаунта | Google Cloud Console → Billing |
| **Что даёт** | Gemini в чате, Drive | Снятие дневных/минутных API-лимитов |
| **Нужна карта в GCP?** | ❌ | ✅ |

**Аналогия:** Купить Netflix Premium не даёт безлимитный интернет. Это разные истории.

---

## 3. Usage Tiers — что это и как переключиться

| Tier | Условие | RPM (flash-lite) | RPD |
|------|---------|-----------------|-----|
| **Free** | Нет billing | 30 | 1500 |
| **Tier 1** | Billing включён | 4000 | unlimited |
| **Tier 2** | $250+ потрачено | выше | выше |
| **Tier 3** | $1000+ потрачено | выше | выше |

**Как перейти Free → Tier 1 (мгновенно):**
1. https://console.cloud.google.com → выбрать проект ключа
2. `Billing` → `Link a billing account` → привязать карту
3. Tier переключится автоматически (обычно мгновенно)
4. Проверить: https://aistudio.google.com/rate-limit

---

## 4. Как читать 429-ошибку из Gemini

В теле ошибки есть поле `quotaId` — оно говорит ВСЁ:

```json
"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
                                                              ^^^^^^^^
                                                         → Free Tier!
                                                         → Нужен billing
```

vs при платном tier:
```json
"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-Tier1"
```

---

## 5. Диагностический скрипт — тест всех ключей

```bash
# Запустить на сервере: проверяет каждый ключ и показывает HTTP статус
for i in "" _2 _3 _4 _5 _6; do
  KEY=$(grep "GEMINI_API_KEY${i}=" ~/ai-design-workspace/deploy/.env | cut -d= -f2)
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${KEY}" \
    -H "Content-Type: application/json" \
    -d '{"contents":[{"parts":[{"text":"hi"}]}]}')
  echo "GEMINI_API_KEY${i}: HTTP ${STATUS}"
done
```

**Расшифровка статусов:**
- `200` — ключ работает, квота не исчерпана
- `429` — rate limit (исчерпана квота проекта)
- `400` — неверный формат запроса (с ключом всё ок)
- `403` — ключ отозван или billing не настроен

---

## 6. Vertex AI vs Gemini API — в чём разница

В логах появлялось: `vertex_ai_betaException`.

| | Gemini API (прямой) | Vertex AI Gemini |
|---|---|---|
| **Endpoint** | `generativelanguage.googleapis.com` | `*.googleapis.com/v1/projects/...` |
| **Auth** | API Key | Service Account |
| **Billing** | через AI Studio | через Google Cloud |
| **Лимиты** | quota per project | quota per region |

Если LiteLLM использует Vertex AI endpoint — это другая система квот.
Проверить в `antigravity.json`: поле `api_base`.

---

## 7. Правильная архитектура Key Pool для максимальной надёжности

```
Ключ 1 (Аккаунт A, Project A) ─┐
Ключ 2 (Аккаунт B, Project B) ─┤── Независимые бакеты квот → ротация работает!
Ключ 3 (Аккаунт C, Project C) ─┘

НЕ ТАК:
Ключ 1 (Account A, Project A) ─┐
Ключ 2 (Account A, Project A) ─┤── Один бакет → ротация бесполезна при RPD
Ключ 3 (Account A, Project A) ─┘
```

**Ideal setup:** 1 ключ = 1 отдельный Google-аккаунт = 1 GCP Project с billing.

---

## 8. Связь с MLOps/резюме

В MLOps-мире управление API-лимитами и multi-tenant quota management — это:
- **Rate Limiting & Throttling** — понимание как работают лимиты провайдеров
- **Vendor Resilience** — почему Circuit Breaker+Fallback важны для prod систем
- **Cost Optimization** — правильная настройка paid tier vs free tier

В резюме: "Implemented multi-account API key rotation with per-project quota isolation
for Google Gemini API, preventing RPD exhaustion through independent billing account
distribution."
