# Text Formatting Guide for Excel/Google Sheets

This guide explains how to format text in your Google Sheets to display **bold text** and use **new lines/paragraphs** in the bot's catalog and product cards.

## Supported Formatting

The bot supports the following formatting options:

### 1. **Bold Text**
To make text bold, wrap it with double asterisks: `**text**`

**Examples:**
- `**Название курса**` → **Название курса** (bold)
- `**Цена:** 1000 руб.` → **Цена:** 1000 руб.
- `Это **важный** текст` → Это **важный** текст

### 2. **New Lines and Paragraphs**
To create a new line, simply press `Enter` in the cell. The bot will preserve all line breaks.

**Examples:**
```
**Название курса**

Описание курса на первой строке.
Описание на второй строке.

Дополнительная информация.
```

This will display as:
- **Название курса** (bold, on its own line)
- Empty line (paragraph break)
- Description text on separate lines
- Another paragraph break
- Additional information

## Where to Apply Formatting

### Course Catalog Sheet
In your **Courses** sheet (the sheet with course data), you can format:

1. **`name` column** - Course name
   - Example: `**Базовый курс макияжа**`
   - Example with newlines: `**Базовый курс макияжа**\nПодзаголовок`

2. **`description` column** - Course description
   - Example:
     ```
     **Что вы узнаете:**
     
     • Основы макияжа
     • Работа с кистями
     • Техники нанесения
     
     **Длительность:** 10 уроков
     ```

### Texts Sheet
In your **Texts** sheet (the sheet with bot messages), you can format:

1. **`catalog_text`** - Text displayed in the catalog
   - Example:
     ```
     **Добро пожаловать в каталог!**
     
     Выберите интересующий вас курс из списка ниже.
     ```

## How to Format in Google Sheets

### Method 1: Direct Typing (Recommended)
Simply type the formatting directly in the cell:

1. Open your Google Sheet
2. Click on the cell you want to edit
3. Type your text with `**` for bold sections
4. Press `Enter` to create new lines within the same cell
5. The formatting will be preserved when the bot reads the data

**Example cell content:**
```
**Курс по макияжу**

Подробное описание курса.
Вторая строка описания.

**Преимущества:**
• Пункт 1
• Пункт 2
```

### Method 2: Using CHAR(10) for Line Breaks
If you need to use formulas, you can use `CHAR(10)` for line breaks:

```
="**Название**" & CHAR(10) & "Описание" & CHAR(10) & CHAR(10) & "Дополнительно"
```

## Important Notes

1. **Double Asterisks Only**: Use `**text**` for bold. Single asterisks `*text*` will also work, but `**text**` is recommended.

2. **Line Breaks**: Simply press `Enter` in the cell to create new lines. Google Sheets will preserve them.

3. **No HTML Tags**: Don't use HTML tags like `<b>`, `<br>`, etc. Use the markdown-style formatting instead.

4. **Special Characters**: The following characters will be automatically escaped:
   - `<` → `&lt;`
   - `>` → `&gt;`
   - `&` → `&amp;`

5. **Testing**: After updating your Google Sheet, the bot will automatically use the new formatting when it fetches the data (usually on next request or after cache refresh).

## Examples

### Example 1: Course Name with Bold
**Cell content:**
```
**Профессиональный курс макияжа**
```

**Result in bot:**
**Профессиональный курс макияжа** (displayed in bold)

### Example 2: Course Description with Formatting
**Cell content:**
```
**Описание курса:**

Этот курс научит вас основам профессионального макияжа.

**Что включено:**
• 15 видеоуроков
• Практические задания
• Обратная связь от преподавателя

**Длительность:** 30 дней
```

**Result in bot:**
- **Описание курса:** (bold)
- Empty line
- Description text
- Empty line
- **Что включено:** (bold)
- Bullet points
- Empty line
- **Длительность:** 30 дней (bold)

### Example 3: Catalog Text
**Cell content (in Texts sheet, `catalog_text` key):**
```
**Каталог курсов**

Выберите интересующий вас курс из списка ниже.
Все курсы доступны для покупки.
```

**Result in bot:**
- **Каталог курсов** (bold, on its own line)
- Empty line
- Regular text below

## Troubleshooting

**Problem**: Bold text not showing
- **Solution**: Make sure you're using `**text**` (double asterisks), not single asterisks or HTML tags

**Problem**: Line breaks not working
- **Solution**: Make sure you're pressing `Enter` within the cell (not just moving to the next cell). In Google Sheets, you can press `Ctrl+Enter` (Windows) or `Cmd+Enter` (Mac) to add a line break without leaving the cell.

**Problem**: Formatting looks wrong
- **Solution**: Check that you don't have unmatched asterisks or special characters that might interfere with parsing

## Need Help?

If you encounter any issues with text formatting, check:
1. That you're using `**` for bold (not `*` or HTML)
2. That line breaks are actual line breaks in the cell (not spaces)
3. That the bot has refreshed its cache (try restarting the bot or waiting a few minutes)

