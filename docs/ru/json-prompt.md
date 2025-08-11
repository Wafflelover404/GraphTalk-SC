# Стандарт JSON для SC-Machine v3.0

## 1. Назначение
Стандартизированная структура JSON для:
- Семантического представления технических текстов
- Поддержки сегментации контента
- Совместимости с OSTIS

## 2. Структура файла
```json
{
  "Source content": {
    "full_text": "Полный исходный текст...",
    "segments": {
      "seg_[SHA256]": "Содержание сегмента..."
    }
  },
  "Относится к сегменту": {
    "[концепт]": "seg_[SHA256]"
  },
  "[глагол_отношения]": {
    "[субъект]": "[объект]|['объект1','объект2']"
  },
  "membership": {
    "[узел]": ["атрибут1", "атрибут2"]
  }
}
```

## 3. Спецификация полей

### 3.1 Исходный текст (Обязательно)
```json
"Source content": {
  "full_text": "C++ — язык программирования...",
  "segments": {
    "seg_a1b2c3": "C++ создан Бьёрном Страуструпом...",
    "seg_d4e5f6": "Основные особенности..."
  }
}
```

### 3.2 Отношения сегментов
```json
"Относится к сегменту": {
  "C++": "seg_a1b2c3",
  "ООП": ["seg_a1b2c3", "seg_d4e5f6"]
}
```

### 3.3 Семантические отношения
```json
"Является": {
  "C++": "язык программирования"
},
"Поддерживает": {
  "C++": ["ООП", "обобщённое программирование"]
}
```

## 4. Правила нормализации

### 4.1 Идентификаторы узлов
```python
normalize_identifier("Объектно-ориентированное") → "obektno_orientirovannoe"
normalize_identifier("C++") → "c"
```

## 5. Правила валидации

1. **Структурные**:
   - Должно быть поле `Source content`
   - Все сегменты должны быть связаны

2. **Семантические**:
   - Отношения в инфинитиве
   - Сущности в именительном падеже

## 6. Преобразование в OSTIS

| Компонент JSON       | Тип SC-узла          |
|----------------------|----------------------|
| `[концепт]`          | `sc_node_class`      |
| `[глагол]`           | `sc_node_norel`      |
| `seg_[хэш]`          | `sc_node_struct`     |
```

Key differences between files:
1. **Language**: Full translation of all descriptions
2. **Examples**: Language-specific examples
3. **Field names**: Russian version uses `"Относится к сегменту"` instead of `"Belongs to segment"`
4. **Normalization**: Shows Cyrillic handling in Russian version

Both standards maintain identical technical requirements while being language-adapted.