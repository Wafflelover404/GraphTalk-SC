# Документация по RAG API

## Обзор
RAG (Retrieval-Augmented Generation) API предоставляет мощный интерфейс для поиска документов и генерации ответов с использованием векторных эмбеддингов и больших языковых моделей. В этой документации описаны настройка, использование и интеграция RAG API.

## Содержание
- [Возможности](#возможности)
- [Быстрый старт](#быстрый-старт)
- [Конечные точки API](#конечные-точки-api)
- [Конфигурация](#конфигурация)
- [Аутентификация](#аутентификация)
- [Примеры](#примеры)
- [Устранение неполадок](#устранение-неполадок)

## Возможности
- Индексация и векторизация документов
- Семантический поиск
- Интеграция с различными LLM-провайдерами
- Поддержка различных форматов документов (PDF, DOCX, TXT, HTML, MD)
- Асинхронная обработка
- Безопасная аутентификация и авторизация

## Быстрый старт
```bash
# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env с вашей конфигурацией

# Запуск API сервера
python -m uvicorn rag_api.main:app --reload
```

## Конечные точки API
### Управление документами
- `POST /api/rag/documents` - Загрузить и проиндексировать новый документ
- `GET /api/rag/documents` - Список всех проиндексированных документов
- `GET /api/rag/documents/{doc_id}` - Получить детали документа
- `DELETE /api/rag/documents/{doc_id}` - Удалить документ

### Поиск и генерация
- `POST /api/rag/search` - Семантический поиск по документам
- `POST /api/rag/generate` - Генерация ответов с использованием RAG
- `POST /api/rag/chat` - Интерактивный чат с контекстом документов

## Конфигурация
Настройка осуществляется через переменные окружения:
```
# Обязательные
GOOGLE_API_KEY=ваш_google_api_key
DATABASE_URL=sqlite:///rag_app.db

# Опциональные
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
CHUNK_SIZE=1500
CHUNK_OVERLAP=300
```

## Аутентификация
Все конечные точки требуют аутентификации с использованием JWT токенов. Укажите токен в заголовке Authorization:
```
Authorization: Bearer <ваш_jwt_токен>
```

## Примеры
### Пример поиска
```python
import requests

url = "http://localhost:8000/api/rag/search"
headers = {
    "Authorization": "Bearer ваш_jwt_токен",
    "Content-Type": "application/json"
}
data = {
    "query": "Какая столица Франции?",
    "top_k": 3
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

### Пример генерации ответа
```python
import requests

url = "http://localhost:8000/api/rag/generate"
headers = {
    "Authorization": "Bearer ваш_jwt_токен",
    "Content-Type": "application/json"
}
data = {
    "query": "Объясните основные концепции RAG",
    "max_tokens": 500
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

## Устранение неполадок
### Распространенные проблемы
1. **Документ не найден**
   - Убедитесь, что документ был успешно загружен и проиндексирован
   - Проверьте логи на наличие ошибок индексации

2. **Ошибка аутентификации**
   - Убедитесь, что ваш JWT токен действителен и не истек
   - Проверьте формат заголовка Authorization

3. **Медленные ответы**
   - Попробуйте увеличить ресурсы сервера
   - Проверьте, правильно ли загружена модель эмбеддингов

### Получение помощи
Для получения дополнительной поддержки создайте issue в нашем [репозитории на GitHub](https://github.com/yourusername/graphtalk-sc/issues).
