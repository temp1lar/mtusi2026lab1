# Лабораторная 1: запуск и проверка

Реализация на C# / ASP.NET Core, цель — оценка **4**. Исходное задание находится в README.md.

**Статус:** сервер собран, публичный smoke и 9 собственных тестов прошли.
Остановка процесса, очистка состояния и отсутствие текста сообщения в логах проверены локально.
**Docker в среде разработки отсутствовал: сборку образа и контейнерные критерии ещё нужно проверить на вашем компьютере.**

## Самая первая команда на Windows

Распакуйте архив. Откройте PowerShell **в папке lab1**, где лежит Dockerfile.
Запустите Docker Desktop, дождитесь готовности Linux containers.

```powershell
python scripts/verify_docker.py
```

Если Python запускается через launcher:

```powershell
py -3 scripts/verify_docker.py
```

На Kubuntu:

```bash
python3 scripts/verify_docker.py
```

Скрипт сам собирает образ из исходников, запускает отдельный контейнер на свободном
локальном порту, ждёт Docker healthcheck, проверяет UID, API, конкурентную запись,
SIGTERM с незавершённым запросом, логи и потерю состояния после перезапуска.
Удаляет только собственный временный контейнер. Образ остаётся для ручного запуска.
Первой сборке нужен интернет для скачивания образов Microsoft. Python 3.9+,
без дополнительных pip-пакетов; make не требуется.

**Пришлите файл `evidence/docker-verification.txt` или текст ошибки.**
Даже после ошибки файл содержит пройденные шаги. Успешный финал:
`PASS all Docker acceptance checks`.

Для этого пути не нужно обновлять установленный .NET: SDK и runtime уже заданы в Dockerfile.

## Ручной запуск для изучения и защиты

```sh
docker build -t mtusi-messenger:lab1 .
```

На Windows:

```powershell
Copy-Item .env.example .env
docker run --name mtusi-messenger-lab1 -p 127.0.0.1:8080:8080 --env-file .env mtusi-messenger:lab1
```

На Linux:

```bash
cp .env.example .env
docker run --name mtusi-messenger-lab1 -p 127.0.0.1:8080:8080 --env-file .env mtusi-messenger:lab1
```

Во втором терминале, в этой же папке:

```sh
python tests/smoke.py
python tests_own/test_api.py
```

На Linux замените `python` на `python3`, либо выполните `make test-all`.
Для другой установки сервера: `python tests_own/test_api.py --base-url http://localhost:8080`.

Остановка и повторный запуск:

```sh
docker stop --time 10 mtusi-messenger-lab1
docker start mtusi-messenger-lab1
```

Все пользователи, чаты и сообщения после остановки процесса потеряны. Удаление контейнера
для очистки стенда: `docker rm -f mtusi-messenger-lab1`. Volumes и файлы состояния не создаются.

## Без Docker

Нужен **SDK 10.0.403** — версия закреплена в global.json. Установленный ранее SDK 9.0.118
не собирает net10.0. Можно установить SDK 10 параллельно, не удаляя SDK 9.

```sh
dotnet run --project src/Messenger
```

Одна команда для автоматической локальной проверки (Linux/macOS, включая настоящий SIGTERM):

```sh
python3 scripts/verify_local.py
```

На Windows используйте Docker-проверку для SIGTERM: `Popen.terminate()` в Windows
не эквивалентен POSIX SIGTERM. Для обычного API достаточно `dotnet run` и двух тестовых команд выше.
`dotnet run` сам не читает `.env`: переменные задаются оболочкой; без них используются значения по умолчанию.

## Что читать дальше

1. `docs/EXPLANATION_RU.md` — как устроен код, библиотеки, план расширения, вопросы защиты.
2. `docs/ERRORS_RU.md` — реальные ошибки и способы исправления.
3. `REPORT.md` — отчёт, таблица критериев и честный статус проверок.
4. `evidence/local-verification.txt` — итоговый фактический вывод тестов.

Перед сдачей заполните своё имя, группу и ссылку на commit/PR в REPORT.md.
После успешной Docker-проверки дополните отчёт полученными результатами.
