# Технический обзор

## Компоненты

| Компонент | Роль | Стек |
|---|---|---|
| [`lab-bridge`](https://github.com/bioexperiment-lab-devices/lab-bridge) | Docker Compose стек на стороне VPS: публичная точка входа, среда notebooks, tunnel server, observability. | Docker Compose, Caddy, JupyterLab, chisel, Loki, Grafana. |
| [`serialhop`](https://github.com/bioexperiment-lab-devices/serialhop) | Агент на лабораторной машине: предоставляет доступ к serial-устройствам через HTTP, дозванивается до VPS через chisel. | Один Go-бинарь (Windows service). |
| [`bioexperiment_suite`](https://github.com/khamitovdr/bioexperiment_suite) | Python-библиотека, используемая в notebooks; HTTP-клиент к `serialhop`. | Python, `httpx`, `loguru`. |

Живые endpoint'ы: [JupyterLab](https://111.88.145.138/lab) · [Grafana](https://111.88.145.138/grafana/).

## Топология

Лабораторный ПК открывает исходящее chisel-соединение к VPS. Эта же chisel-сессия несёт:

- **Reverse tunnels** — локальный REST API каждого lab-агента публикуется в docker-сеть `labnet`, доступен из среды notebooks как `http://chisel:<port>`.
- **Forward tunnel** — `lab_pc:127.0.0.1:3100 → loki:3100`, используется для отправки логов агента в Loki.

В лабораторной сети нет открытых входящих портов. Авторизация chisel — через allowlist пар user/password, по одной на клиента, управляется на VPS.

## `lab-bridge`

Один Docker Compose стек в сети `labnet`:

- **caddy** — публичный на 80/443; TLS через Let's Encrypt; проксирует `/grafana/*` → grafana, всё остальное → jupyter.
- **jupyter** — JupyterLab; cookie-based авторизация по общему паролю.
- **chisel** — публичный на сконфигурированном listen-порту; allowlist по клиентам.
- **loki** — только внутренний, без публикуемого порта.
- **grafana** — только внутренняя, доступна через caddy по `/grafana/`. Provisioned Loki datasource и дашборд "Lab client logs" (live tail, объём логов по клиентам, ошибки, текущие версии).

**Поверхность для оператора**:

- `Taskfile.yml` оборачивает `scripts/{provision,deploy,secrets,ops,doctor}.sh`.
- `config.yaml` (в gitignore, копия `config.example.yaml`) хранит реквизиты VPS, listen-порт chisel, retention и т.д.
- Шаблоны в `compose/` рендерятся через `yq` (сборка mikefarah).
- Секреты управляются через `task secrets:*`: пароль jupyter, пароль grafana admin, chisel-учётки по клиентам.
- Тесты: наборы на `bats-core` в `tests/`, прогоняются против fake-VPS Docker-контейнера; `task test`.

**Первичный запуск**:

```bash
cp config.example.yaml config.yaml      # отредактировать
task secrets:set-jupyter-password
task secrets:set-grafana-password
task secrets:add-client -- <name> <port>
task provision
task deploy
```

**Ops-точки входа**: `task ops:logs:loki`, `task ops:logs:grafana`, `task ops:loki-disk`.

## `serialhop`

Один статический Go-бинарь, target по умолчанию — Windows/amd64; результат — `dist/SerialHop.exe`.

**Режимы работы** (определяются автоматически по контексту запуска):

| Запущено через | Режим |
|---|---|
| SCM | Service worker |
| Двойной клик | Панель управления (lxn/walk GUI) |
| `--admin-action=...` | Внутренняя SCM-операция (повторный вход через UAC) |
| `--foreground` | Консольный developer-режим (JSON-логи в stdout) |

**Service**: регистрируется как `SerialHop`, auto-start при загрузке системы, работает под `LocalSystem`. Install / uninstall / restart — из панели управления.

**REST API** — привязывается к `127.0.0.1`, доступен с VPS только через reverse tunnel:

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | `/discover` | Свежее обнаружение; деструктивно. |
| `GET` | `/devices` | Кэшированный список устройств. |
| `POST` | `/devices/{id}/command` | Отправить сырые байты; опциональное чтение ответа. Query-параметры: `wait_for_response`, `expected_response_bytes`, `timeout_ms`, `inter_byte_ms`. |

**Типы устройств**: `pump` (type code 10), `valve` (30), `densitometer` (70). Discovery опрашивает порты универсальным probe `[1, 2, 3, 4, 0]`.

**Файлы** (рядом с `.exe`):

- `SerialHop_config.yaml` — конфиг (chisel host/port/user/pass и т.д.).
- `SerialHop.log` — slog JSON, ротация 10 MB × 3.
- `SerialHop_stderr.log` — состояние chisel и panic traces, такая же ротация.

**Стриминг логов в Loki** (только в service-режиме; включается, если задан `chisel.user`):

- Отслеживает оба on-disk лог-файла. On-disk файлы остаются durable-записью; Loki — queryable-зеркало.
- In-memory ring buffer: 10 000 записей, drop-oldest при переполнении.
- Отправляет gzipped JSON, батчи ≤ 500 записей или 2 с; backoff на 5xx, drop-batch на 4xx.
- Лейблы: `client` (chisel user), `stream` (`stdout`/`stderr`), `service=serialhop`, `version`.

**Сборка**: `task build`. Встраивает иконку, UAC-манифест (`asInvoker`) и version metadata через `goversioninfo`. Автоматически увеличивает minor-версию при dirty tree; версия прошивается через `-ldflags -X` и показывается в заголовке панели.

**Установка на машину**:

1. Скопировать `SerialHop.exe` в директорию установки (например, `C:\Tools\SerialHop\`).
2. Запустить; отредактировать `SerialHop_config.yaml` (`chisel.remote_port`, `chisel.user`, `chisel.pass`).
3. Нажать **Install** в панели; подтвердить UAC.

## `bioexperiment_suite`

Python-пакет. Состояние после миграции — на ветке HTTP-транспорта; полный контракт описан в [HTTP client design spec](https://github.com/khamitovdr/bio_tools/blob/main/docs/superpowers/specs/2026-04-27-lab-devices-http-client-design.md). `main` всё ещё несёт легаси-реализацию с прямым serial; ветки расходятся, runtime-переключателя между ними нет.

**Структура**:

```
src/bioexperiment_suite/
├── interfaces/
│   ├── lab_devices_client.py   # LabDevicesClient, DiscoveredDevices, exceptions
│   ├── pump.py
│   ├── densitometer.py
│   └── valve.py                # placeholder, без методов
├── experiment/                 # transport-agnostic, не менялся
├── device_interfaces.json      # клиентский словарь байтовых команд
└── loader.py
```

**Публичный API** (`bioexperiment_suite.interfaces`):

- `LabDevicesClient(port, host="chisel", request_timeout_sec=5.0)` — владеет одним `httpx.Client`; context manager.
- Методы: `discover()`, `list_devices()`, `send_command(...)`, `close()`.
- Возвращает `DiscoveredDevices(pumps, densitometers, valves, discovered_at)`.
- Классы устройств (`Pump`, `Densitometer`, `Valve`) создаются через `discover()` / `list_devices()`, а не напрямую.

**Иерархия исключений**:

| Исключение | HTTP | Серверный `error` code |
|---|---|---|
| `InvalidRequest` | 400 | invalid request body / query param |
| `DeviceNotFound` | 404 | device not found |
| `DeviceBusy` | 409 | device busy |
| `DiscoveryInProgress` | 409 | discovery in progress |
| `DiscoveryFailed` | 500 | discovery failed |
| `DeviceUnreachable` | 503 | device unreachable |
| `DeviceIOFailed` | 503 | device i/o failed |
| `DeviceIdentityChanged` | 503 | device identity changed |
| `TransportError` | 0 | `connection error` / `read timeout` / `invalid response` |

Все наследуются от `LabDevicesError(status, code, detail)`. Никакого автоматического retry, никаких silent fallbacks.

**Особенности поведения**:

- `Pump.__init__` делает по одному калибровочному round-trip на каждый насос при каждом вызове `discover()` / `list_devices()`.
- `Densitometer.measure_optical_density` отправляет start, спит 3 с на стороне клиента, читает.
- Политика query-параметров `send_command`: `expected_response_bytes` опускается, когда `wait_for_response=False`; `timeout_ms` / `inter_byte_ms` опускаются, если не переданы явно (применяются дефолты сервера).
- Никакого клиентского кэширования `/devices` (сервер уже кэширует).
- Async API нет; только синхронный `httpx.Client`.

**Зависимости**: `httpx ^0.28`, `loguru`. Тесты: `pytest` с `httpx.MockTransport` (unit), фейки для тестов классов устройств, ручная интеграция против реального lab-агента.

**Использование в notebook**:

```python
client = LabDevicesClient(port=9001)   # host по умолчанию "chisel"
devices = client.discover()
for pump in devices.pumps:
    pump.pour_in_volume(5.0)
od = devices.densitometers[0].measure_optical_density()
```

## Репозитории и endpoint'ы

- `lab-bridge`: <https://github.com/bioexperiment-lab-devices/lab-bridge>
- `serialhop`: <https://github.com/bioexperiment-lab-devices/serialhop>
- `bioexperiment_suite`: <https://github.com/khamitovdr/bioexperiment_suite>
- Migration spec: <https://github.com/khamitovdr/bio_tools/blob/main/docs/superpowers/specs/2026-04-27-lab-devices-http-client-design.md>
- JupyterLab: <https://111.88.145.138/lab>
- Grafana: <https://111.88.145.138/grafana/>
