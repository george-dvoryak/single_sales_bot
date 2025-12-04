# Text Formatting Guide for Excel/Google Sheets

This guide explains how to format text in your Google Sheets to display **bold text** and use **new lines/paragraphs** in the bot's catalog and product cards.

## Supported Formatting

The bot supports HTML formatting directly. Use HTML tags and `\n` for newlines.

### 1. **Bold Text**
To make text bold, use HTML `<b>` tags: `<b>text</b>`

**Examples:**
- `<b>Название курса</b>` → **Название курса** (bold)
- `<b>Цена:</b> 1000 руб.` → **Цена:** 1000 руб.
- `Это <b>важный</b> текст` → Это **важный** текст

### 2. **New Lines and Paragraphs**
To create a new line, type `\n` (backslash followed by n) in your cell. The bot will convert `\n` to actual line breaks.

**Important:** Since pressing Enter in Google Sheets moves to the next cell, use `\n` for line breaks instead.

**Examples:**
```
<b>Название курса</b>\n\nОписание курса на первой строке.\nОписание на второй строке.\n\nДополнительная информация.
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
   - Example: `<b>Базовый курс макияжа</b>`
   - Example with newlines: `<b>Базовый курс макияжа</b>\nПодзаголовок`

2. **`description` column** - Course description
   - Example:
     ```
     <b>Что вы узнаете:</b>\n\n• Основы макияжа\n• Работа с кистями\n• Техники нанесения\n\n<b>Длительность:</b> 10 уроков
     ```

### Texts Sheet
In your **Texts** sheet (the sheet with bot messages), you can format:

1. **`catalog_text`** - Text displayed in the catalog
   - Example:
     ```
     <b>Добро пожаловать в каталог!</b>\n\nВыберите интересующий вас курс из списка ниже.
     ```

## How to Format in Google Sheets

### Method 1: Direct Typing (Recommended)
Simply type the formatting directly in the cell:

1. Open your Google Sheet
2. Click on the cell you want to edit
3. Type your text with HTML tags like `<b>` for bold sections
4. Type `\n` (backslash followed by n) for new lines
5. The formatting will be preserved when the bot reads the data

**Example cell content:**
```
<b>Курс по макияжу</b>\n\nПодробное описание курса.\nВторая строка описания.\n\n<b>Преимущества:</b>\n• Пункт 1\n• Пункт 2
```

### Method 2: Using CHAR(10) in Formulas
If you need to use formulas, you can use `CHAR(10)` for line breaks:

```
="<b>Название</b>" & CHAR(10) & "Описание" & CHAR(10) & CHAR(10) & "Дополнительно"
```

**Note:** When using formulas, `CHAR(10)` will be converted to `\n` automatically, which the bot will then convert to actual newlines.

## Important Notes

1. **HTML Tags**: Use HTML tags directly:
   - `<b>text</b>` for **bold**
   - `<i>text</i>` for *italic*
   - `<u>text</u>` for <u>underline</u>
   - `<s>text</s>` for ~~strikethrough~~
   - `<code>text</code>` for `code`
   - `<pre>text</pre>` for preformatted text

2. **Line Breaks**: Type `\n` (backslash followed by n) for new lines. Since pressing Enter in Google Sheets moves to the next cell, use `\n` instead. The bot will convert `\n` to actual line breaks.

3. **Multiple Newlines**: Use `\n\n` for paragraph breaks (empty lines between paragraphs).

4. **Special Characters**: The following characters will be automatically escaped:
   - `<` → `&lt;`
   - `>` → `&gt;`
   - `&` → `&amp;`

5. **Testing**: After updating your Google Sheet, the bot will automatically use the new formatting when it fetches the data (usually on next request or after cache refresh).

## Examples

### Example 1: Course Name with Bold
**Cell content:**
```
<b>Профессиональный курс макияжа</b>
```

**Result in bot:**
**Профессиональный курс макияжа** (displayed in bold)

### Example 2: Course Description with Formatting
**Cell content:**
```
<b>Описание курса:</b>\n\nЭтот курс научит вас основам профессионального макияжа.\n\n<b>Что включено:</b>\n• 15 видеоуроков\n• Практические задания\n• Обратная связь от преподавателя\n\n<b>Длительность:</b> 30 дней
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
<b>Каталог курсов</b>\n\nВыберите интересующий вас курс из списка ниже.\nВсе курсы доступны для покупки.
```

**Result in bot:**
- **Каталог курсов** (bold, on its own line)
- Empty line
- Regular text below

## Troubleshooting

**Problem**: Bold text not showing
- **Solution**: Make sure you're using HTML tags like `<b>text</b>`, not markdown `**text**`

**Problem**: Line breaks not working
- **Solution**: 
  1. Make sure you're typing `\n` (backslash followed by n) literally in the cell, not pressing Enter
  2. For paragraph breaks, use `\n\n` (two newlines)
  3. If using formulas with `CHAR(10)`, that will work too
  4. Try refreshing the bot's cache or restarting the bot to pick up changes

**Problem**: Formatting looks wrong
- **Solution**: Check that you don't have unmatched asterisks or special characters that might interfere with parsing

## Need Help?

If you encounter any issues with text formatting, check:
1. That you're using HTML tags like `<b>text</b>` for bold (not markdown `**text**`)
2. That you're typing `\n` literally for line breaks (backslash followed by n)
3. That HTML tags are properly closed (e.g., `<b>text</b>`, not `<b>text`)
4. That the bot has refreshed its cache (try restarting the bot or waiting a few minutes)

