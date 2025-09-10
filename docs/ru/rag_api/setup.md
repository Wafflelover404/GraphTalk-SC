# Руководство по настройке RAG API

## Требования

- Python 3.8 или новее
- pip (менеджер пакетов Python)
- Git
- Аккаунт Google Cloud (для доступа к API Google)

## Установка

1. **Клонируйте репозиторий**
   ```bash
   git clone https://github.com/yourusername/graphtalk-sc.git
   cd graphtalk-sc
   ```

2. **Создайте виртуальное окружение** (рекомендуется)
   ```bash
   python -m venv venv
   source venv/bin/activate  # В Windows: venv\Scripts\activate
   ```

3. **Установите зависимости**
   ```bash
   pip install -r requirements.txt
   ```

4. **Настройте переменные окружения**
   Создайте файл `.env` в корне проекта:
   ```bash
   cp .env.example .env
   ```
   Отредактируйте файл `.env`:
   ```
   # Обязательные
   GOOGLE_API_KEY=ваш_google_api_key
   DATABASE_URL=sqlite:///rag_app.db
   
   # Опциональные
   EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
   CHUNK_SIZE=1500
   CHUNK_OVERLAP=300
   DEBUG=True
   ```

## Запуск API

### Режим разработки
```bash
uvicorn rag_api.main:app --reload
```

### Продакшн-режим
Для продакшена используйте ASGI-сервер с несколькими воркерами:
```bash
uvicorn rag_api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Использование Docker
1. Соберите Docker-образ:
   ```bash
   docker build -t rag-api .
   ```

2. Запустите контейнер:
   ```bash
   docker run -p 8000:8000 --env-file .env rag-api
   ```

## Первоначальная настройка

1. **Инициализация базы данных**
   ```bash
   python -m rag_api.db.init_db
   ```

2. **Создание суперпользователя** (для админки)
   ```bash
   python -m rag_api.scripts.create_superuser
   ```

## Параметры конфигурации

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `GOOGLE_API_KEY` | API-ключ Google Cloud | - |
| `DATABASE_URL` | URL подключения к БД | `sqlite:///rag_app.db` |
| `EMBEDDING_MODEL` | Модель для эмбеддингов | `sentence-transformers/all-mpnet-base-v2` |
| `CHUNK_SIZE` | Размер фрагментов текста | `1500` |
| `CHUNK_OVERLAP` | Перекрытие фрагментов | `300` |
| `DEBUG` | Режим отладки | `False` |
| `SECRET_KEY` | Секретный ключ для JWT | Генерируется автоматически |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Время жизни JWT токена | `30` |

### Документация API
После запуска API доступны:
- Интерактивная документация: http://localhost:8000/docs
- Альтернативная документация: http://localhost:8000/redoc

## Обновление API

1. Получите последние изменения:
   ```bash
   git pull origin main
   ```

2. Обновите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

3. Примените миграции БД (если есть):
   ```bash
   alembic upgrade head
   ```

4. Перезапустите сервер API.
