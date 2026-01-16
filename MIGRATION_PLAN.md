# План миграции Auto-Claude → Auto-iFlow

## Обзор проекта

**Цель:** Полностью заменить зависимость от Claude (claude-agent-sdk, Claude Code CLI, Claude OAuth) на iFlow CLI (iflow-cli-sdk, iFlow CLI).

**Ветка:** `iflow-cli-integration`

---

## Текущая архитектура (Claude)

### Бэкенд (Python)
- **claude-agent-sdk** - основной SDK для AI взаимодействий
- **ClaudeSDKClient** - клиент для создания агентских сессий
- **ClaudeAgentOptions** - конфигурация агентов
- **OAuth аутентификация** - через Claude Code CLI токены

### Фронтенд (Electron/TypeScript)
- **Claude Code CLI** - детекция и валидация
- **Claude профили** - управление аккаунтами
- **Claude OAuth** - аутентификация пользователей

---

## Целевая архитектура (iFlow)

### Бэкенд (Python)
- **iflow-cli-sdk** - Python SDK для iFlow
- **IFlowClient** - клиент для AI взаимодействий
- **IFlowOptions** - конфигурация (approval_mode, agents, etc.)
- **iFlow API Key** - аутентификация

### Фронтенд (Electron/TypeScript)
- **iFlow CLI** - детекция (`@iflow-ai/iflow-cli`)
- **iFlow профили** - управление настройками
- **iFlow API Key** - аутентификация

---

## Дорожная карта

### Фаза 1: Анализ и планирование ✅
- [x] Изучение структуры Auto-Claude
- [x] Изучение iFlow CLI и SDK
- [x] Создание плана миграции
- [x] Создание ветки `iflow-cli-integration`

### Фаза 2: Бэкенд - Базовая инфраструктура
**Приоритет: ВЫСОКИЙ**

#### 2.1 Обновить requirements.txt
```diff
- claude-agent-sdk>=0.1.16
+ iflow-cli-sdk>=0.1.0
```

#### 2.2 Создать core/iflow_client.py
Новый модуль для работы с iFlow SDK:
- `create_iflow_client()` - фабрика клиентов
- `IFlowClientWrapper` - обёртка с совместимым API
- Поддержка approval modes (DEFAULT, AUTO_EDIT, YOLO, PLAN)

#### 2.3 Переписать core/auth.py
```python
# Было (Claude)
CLAUDE_CODE_OAUTH_TOKEN
get_token_from_keychain()  # macOS Keychain

# Станет (iFlow)
IFLOW_API_KEY
get_iflow_api_key()  # ~/.iflow/settings.json
```

#### 2.4 Обновить core/client.py
- Заменить `from claude_agent_sdk import ...` на `from iflow_sdk import ...`
- Заменить `ClaudeSDKClient` на `IFlowClient`
- Обновить `create_client()` для iFlow
- Обновить детекцию CLI (`find_claude_cli()` → `find_iflow_cli()`)

#### 2.5 Обновить core/simple_client.py
- Простой клиент для одиночных запросов
- Использовать `iflow_sdk.query()`

### Фаза 3: Бэкенд - Агенты
**Приоритет: ВЫСОКИЙ**

#### 3.1 Обновить agents/session.py
- Заменить `ClaudeSDKClient` на `IFlowClient`
- Адаптировать создание сессий

#### 3.2 Обновить agents/tools_pkg/
- `registry.py` - заменить `create_sdk_mcp_server`
- `tools/memory.py` - заменить `@tool` декоратор
- `tools/progress.py` - заменить `@tool` декоратор
- `tools/subtask.py` - заменить `@tool` декоратор

#### 3.3 Обновить qa/reviewer.py и qa/fixer.py
- Заменить импорты Claude SDK
- Адаптировать для iFlow

### Фаза 4: Бэкенд - Интеграции
**Приоритет: СРЕДНИЙ**

#### 4.1 Обновить runners/
- `ai_analyzer/claude_client.py` → `ai_analyzer/iflow_client.py`
- `github/batch_issues.py` - заменить проверку SDK
- `github/services/` - обновить все сервисы
- `insights_runner.py` - заменить клиент

#### 4.2 Обновить integrations/
- `linear/updater.py` - заменить Claude клиент

### Фаза 5: Фронтенд - CLI Manager
**Приоритет: ВЫСОКИЙ**

#### 5.1 Обновить cli-tool-manager.ts
```typescript
// Было
export type CLITool = 'python' | 'git' | 'gh' | 'claude';

// Станет
export type CLITool = 'python' | 'git' | 'gh' | 'iflow';
```

Обновить пути детекции:
```typescript
// Было
'/opt/homebrew/bin/claude'
'~/.local/bin/claude'

// Станет
'/opt/homebrew/bin/iflow'
'~/.local/bin/iflow'
```

#### 5.2 Переименовать claude-cli-utils.ts → iflow-cli-utils.ts
- Обновить все функции для iFlow

### Фаза 6: Фронтенд - Профили и Auth
**Приоритет: ВЫСОКИЙ**

#### 6.1 Переименовать claude-profile/ → iflow-profile/
- `profile-storage.ts` - хранение настроек iFlow
- `rate-limit-manager.ts` - управление лимитами
- `token-encryption.ts` - шифрование API ключей
- `usage-monitor.ts` - мониторинг использования

#### 6.2 Обновить IPC handlers
- `claude-code-handlers.ts` → `iflow-handlers.ts`
- Обновить все обработчики

### Фаза 7: Фронтенд - UI компоненты
**Приоритет: СРЕДНИЙ**

#### 7.1 Обновить компоненты с Claude брендингом
- `ClaudeCodeStatusBadge.tsx` → `IFlowStatusBadge.tsx`
- `RateLimitModal.tsx` - убрать ссылки на claude.ai
- `SDKRateLimitModal.tsx` - обновить
- `AuthStatusIndicator.tsx` - обновить

#### 7.2 Обновить настройки и онбординг
- `settings/ProfileList.tsx` - убрать Anthropic
- `settings/ProfileEditDialog.tsx` - обновить провайдеры
- `onboarding/GraphitiStep.tsx` - обновить провайдеры

### Фаза 8: Документация
**Приоритет: СРЕДНИЙ**

#### 8.1 Обновить README.md
```markdown
## Requirements
- ~~Claude Pro/Max subscription~~
- ~~Claude Code CLI~~
+ **iFlow CLI** - `npm install -g @iflow-ai/iflow-cli`
+ **iFlow API Key** - Бесплатно на iflow.cn
```

#### 8.2 Переименовать CLAUDE.md → IFLOW.md
- Обновить все инструкции
- Заменить примеры кода

### Фаза 9: Тестирование
**Приоритет: ВЫСОКИЙ**

#### 9.1 Обновить тесты
- Заменить моки Claude на iFlow
- Обновить фикстуры

#### 9.2 Запустить тесты
- Backend: `pytest tests/`
- Frontend: `npm test`

---

## Ключевые файлы для изменения

### Бэкенд (apps/backend/)
| Файл | Изменения |
|------|-----------|
| `requirements.txt` | claude-agent-sdk → iflow-cli-sdk |
| `core/client.py` | Основной клиент |
| `core/auth.py` | Аутентификация |
| `core/simple_client.py` | Простой клиент |
| `agents/session.py` | Сессии агентов |
| `agents/tools_pkg/*.py` | Инструменты |
| `qa/reviewer.py` | QA ревьюер |
| `qa/fixer.py` | QA фиксер |
| `runners/ai_analyzer/` | AI анализатор |
| `runners/github/` | GitHub интеграция |
| `integrations/linear/` | Linear интеграция |

### Фронтенд (apps/frontend/src/)
| Файл | Изменения |
|------|-----------|
| `main/cli-tool-manager.ts` | CLI детекция |
| `main/claude-cli-utils.ts` | CLI утилиты |
| `main/claude-profile/` | Профили |
| `main/ipc-handlers/claude-code-handlers.ts` | IPC |
| `renderer/components/ClaudeCodeStatusBadge.tsx` | UI |
| `renderer/components/settings/` | Настройки |
| `renderer/components/onboarding/` | Онбординг |

---

## Сравнение API

### Создание клиента
```python
# Claude (было)
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
client = ClaudeSDKClient(options=ClaudeAgentOptions(
    model="claude-sonnet-4-5-20250929",
    allowed_tools=["bash", "fs"],
))

# iFlow (станет)
from iflow_sdk import IFlowClient, IFlowOptions, ApprovalMode
async with IFlowClient(IFlowOptions(
    approval_mode=ApprovalMode.YOLO,
)) as client:
    await client.send_message("...")
```

### Простой запрос
```python
# Claude (было)
from claude_agent_sdk import query
response = query("What is 2+2?")

# iFlow (станет)
from iflow_sdk import query
response = await query("What is 2+2?")
```

### Аутентификация
```python
# Claude (было)
token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")

# iFlow (станет)
api_key = os.environ.get("IFLOW_API_KEY")
# или из ~/.iflow/settings.json
```

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Несовместимость API | Средняя | Создать адаптер/обёртку |
| Отсутствие функций в iFlow | Низкая | Реализовать недостающее |
| Проблемы с async/await | Средняя | Рефакторинг на async |
| Тесты не проходят | Высокая | Постепенное обновление |

---

## Оценка времени

| Фаза | Оценка |
|------|--------|
| Фаза 2: Базовая инфраструктура | 4-6 часов |
| Фаза 3: Агенты | 3-4 часа |
| Фаза 4: Интеграции | 2-3 часа |
| Фаза 5: CLI Manager | 2-3 часа |
| Фаза 6: Профили и Auth | 3-4 часа |
| Фаза 7: UI компоненты | 2-3 часа |
| Фаза 8: Документация | 1-2 часа |
| Фаза 9: Тестирование | 2-4 часа |
| **Итого** | **19-29 часов** |

---

## Следующие шаги

1. ✅ Создать ветку `iflow-cli-integration`
2. ⏳ Начать с Фазы 2.1 - обновить requirements.txt
3. ⏳ Создать базовый iFlow клиент
4. ⏳ Постепенно обновлять компоненты
5. ⏳ Тестировать каждое изменение
