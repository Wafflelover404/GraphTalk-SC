# Справочник по API RAG

## Управление документами

### Загрузка и индексация документа
```http
POST /api/rag/documents
```
Загружает документ для обработки и индексации в системе RAG.

**Заголовки запроса**
```
Content-Type: multipart/form-data
Authorization: Bearer <jwt_токен>
```

**Данные формы**
- `file` (обязательный): Файл документа для загрузки (PDF, DOCX, TXT, HTML, MD)
- `metadata` (опционально): JSON строка с дополнительными метаданными
  - `title`: Название документа
  - `description`: Описание документа
  - `tags`: Массив тегов

**Ответ**
```json
{
  "id": "doc_123",
  "filename": "example.pdf",
  "status": "processing",
  "created_at": "2023-01-01T12:00:00Z"
}
```

### Список документов
```http
GET /api/rag/documents
```
Возвращает список всех проиндексированных документов с постраничной навигацией.

**Параметры запроса**
- `page`: Номер страницы (по умолчанию: 1)
- `limit`: Количество элементов на странице (по умолчанию: 10, максимум: 100)
- `status`: Фильтр по статусу (processing, completed, failed)

**Ответ**
```json
{
  "items": [
    {
      "id": "doc_123",
      "filename": "example.pdf",
      "status": "completed",
      "created_at": "2023-01-01T12:00:00Z",
      "page_count": 42
    }
  ],
  "total": 1,
  "page": 1,
  "pages": 1
}
```

## Поиск и генерация

### Семантический поиск
```http
POST /api/rag/search
```
Поиск по проиндексированным документам с использованием семантического сходства.

**Заголовки запроса**
```
Content-Type: application/json
Authorization: Bearer <jwt_токен>
```

**Тело запроса**
```json
{
  "query": "Какая столица Франции?",
  "top_k": 5,
  "min_score": 0.5,
  "document_ids": ["doc_123", "doc_456"]
}
```

**Ответ**
```json
{
  "results": [
    {
      "document_id": "doc_123",
      "text": "Париж - столица Франции.",
      "score": 0.95,
      "page_number": 42,
      "metadata": {
        "title": "Столицы мира"
      }
    }
  ],
  "query_time_ms": 123
}
```

### Генерация ответа
```http
POST /api/rag/generate
```
Генерация ответа с использованием системы RAG.

**Заголовки запроса**
```
Content-Type: application/json
Authorization: Bearer <jwt_токен>
```

**Тело запроса**
```json
{
  "query": "Объясните основные концепции RAG",
  "max_tokens": 1000,
  "temperature": 0.7,
  "document_ids": ["doc_123"],
  "stream": false
}
```

**Ответ**
```json
{
  "response": "RAG (Retrieval-Augmented Generation) объединяет...",
  "sources": [
    {
      "document_id": "doc_123",
      "text": "Системы RAG используют поиск для нахождения...",
      "page_number": 42
    }
  ],
  "generation_time_ms": 1245
}
```

### Чат
```http
POST /api/rag/chat
```
Интерактивный чат с контекстом документов.

**Заголовки запроса**
```
Content-Type: application/json
Authorization: Bearer <jwt_токен>
```

**Тело запроса**
```json
{
  "messages": [
    {"role": "user", "content": "Что такое RAG?"},
    {"role": "assistant", "content": "RAG - это..."},
    {"role": "user", "content": "Как это работает?"}
  ],
  "document_ids": ["doc_123"]
}
```

**Ответ**
```json
{
  "message": "RAG работает, сначала находя...",
  "sources": [
    {
      "document_id": "doc_123",
      "text": "Компонент поиска находит релевантные...",
      "page_number": 42
    }
  ]
}
```

## Ошибки

### 400 Неверный запрос
```json
{
  "detail": "Неверные параметры запроса"
}
```

### 401 Не авторизован
```json
{
  "detail": "Не удалось проверить учетные данные"
}
```

### 404 Не найдено
```json
{
  "detail": "Документ не найден"
}
```

### 500 Внутренняя ошибка сервера
```json
{
  "detail": "Внутренняя ошибка сервера"
}
```
