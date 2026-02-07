# Selector Usage Guide

This guide explains when and how to use `json_schema_extra` selectors with different file type validators.

## 🎯 **When to Use Selectors**

### **✅ RECOMMENDED - Document Structure Validators**

Use selectors when field names don't directly map to document elements:

#### **HTML Structure Validator**
```python
from pydantic import BaseModel, Field

class UserProfile(BaseModel):
    name: str = Field(json_schema_extra={'selector': '.profile-name'})
    email: str = Field(json_schema_extra={'selector': '#user-email'})
    bio: str = Field(json_schema_extra={'selectors': ['.bio-text', '.description', 'p']})  # Fallback chain
```

**HTML Input:**
```html
<div class="profile-name">John Doe</div>
<span id="user-email">john@example.com</span>
<p class="bio-text">Software developer</p>
```

#### **XML Structure Validator**
```python
class BookInfo(BaseModel):
    title: str = Field(json_schema_extra={'selector': '//book/title'})
    author: str = Field(json_schema_extra={'selector': '//book/author/@name'})
    pages: int = Field(json_schema_extra={'selectors': ['//pages', '//page-count']})  # Fallback
```

**XML Input:**
```xml
<book>
    <title>Python Guide</title>
    <author name="Jane Smith" />
    <pages>250</pages>
</book>
```

#### **YAML Structure Validator**
```python
class Config(BaseModel):
    db_host: str = Field(json_schema_extra={'selector': '$.database.host'})
    db_port: int = Field(json_schema_extra={'selector': '$.database.port'})
```

**YAML Input:**
```yaml
database:
  host: localhost
  port: 5432
```

#### **CSV Structure Validator**
```python
class Employee(BaseModel):
    full_name: str = Field(json_schema_extra={'selector': 'Full Name'})  # Column header
    employee_id: int = Field(json_schema_extra={'selector': 'EmpID'})
```

**CSV Input:**
```csv
Full Name,EmpID,Department
John Doe,12345,Engineering
```

#### **Markdown Structure Validator**
```python
class Article(BaseModel):
    title: str = Field(json_schema_extra={'selector': 'h1'})
    summary: str = Field(json_schema_extra={'selector': 'blockquote'})
```

---

## ❌ **NOT RECOMMENDED - Direct Mapping Validators**

### **JSON Structure Validator**

**⚠️ WARNING:** JSON field names map directly to keys. Use aliases instead of selectors.

```python
# ❌ DON'T DO THIS (triggers warning)
class User(BaseModel):
    name: str = Field(json_schema_extra={'selector': 'user_name'})  # Redundant!

# ✅ DO THIS INSTEAD
class User(BaseModel):
    name: str = Field(alias='user_name')  # Use alias for different JSON keys
```

**JSON Input:**
```json
{
    "user_name": "John Doe",  // Maps to 'name' field via alias
    "age": 30
}
```

### **Object Validator**

**No selectors needed** - ObjectValidator is for pure JSON → Pydantic validation without document parsing.

---

## 🔧 **Selector Types Supported**

### **HTML Selectors**
- **CSS Selectors**: `.class`, `#id`, `tag[attr="value"]`
- **XPath**: `//div[@class="name"]`, `/html/body/div[1]`
- **Combination**: `['#primary-name', '.backup-name', 'h1']`

### **XML Selectors**
- **XPath**: `//element`, `//element/@attribute`, `/root/child[1]`
- **Fallback chains**: `['//title', '//name', '//heading']`

### **YAML Selectors**
- **JSONPath**: `$.root.field`, `$.array[0].value`
- **Dot notation**: `database.host`, `users[0].name`

### **CSV Selectors**
- **Column headers**: `"Full Name"`, `"Employee ID"`
- **Column indices**: `0`, `1`, `2` (zero-based)

### **Markdown Selectors**
- **Element types**: `h1`, `h2`, `blockquote`, `code`
- **Position-based**: `h1[0]`, `p[2]`

---

## 🤖 **AI-Powered Selectors**

All validators support AI-powered selector resolution:

```python
class SmartExtraction(BaseModel):
    # AI will try to fix invalid selectors or convert natural language
    title: str = Field(json_schema_extra={'selector': 'find the main heading'})
    price: float = Field(json_schema_extra={'selectors': [
        '.price',           # Try CSS first
        '//span[@class="cost"]',  # Try XPath second  
        'extract the price'       # AI fallback
    ]})
```

**Features:**
- **Auto-correction**: Fixes invalid CSS/XPath syntax
- **Natural language**: Converts descriptions to selectors
- **No prefix needed**: No `ai:` prefix required - automatic detection

---

## 📋 **Best Practices**

### **1. Use Meaningful Field Names**
```python
# ✅ Good
class Product(BaseModel):
    product_name: str = Field(json_schema_extra={'selector': '.title'})
    
# ❌ Avoid
class Product(BaseModel):
    field1: str = Field(json_schema_extra={'selector': '.title'})
```

### **2. Provide Fallback Selectors**
```python
class RobustExtraction(BaseModel):
    title: str = Field(json_schema_extra={'selectors': [
        'h1.main-title',    # Specific selector first
        'h1',               # Generic fallback
        '.title',           # Class fallback
        '[data-title]'      # Attribute fallback
    ]})
```

### **3. Combine with Aliases When Needed**
```python
class FlexibleModel(BaseModel):
    user_name: str = Field(
        alias='name',  # For JSON key mapping
        json_schema_extra={'selector': '.user-display-name'}  # For HTML element finding
    )
```

---

## 🚨 **Common Mistakes**

### **1. Using Selectors with JSON**
```python
# ❌ Wrong - triggers warning
class JSONModel(BaseModel):
    name: str = Field(json_schema_extra={'selector': 'user_name'})

# ✅ Correct - use alias
class JSONModel(BaseModel):
    name: str = Field(alias='user_name')
```

### **2. Forgetting Fallbacks for Fragile Selectors**
```python
# ❌ Fragile - breaks if CSS changes
title: str = Field(json_schema_extra={'selector': 'div.header-container > h1.main-title-text'})

# ✅ Robust - multiple fallbacks
title: str = Field(json_schema_extra={'selectors': [
    'div.header-container > h1.main-title-text',
    'h1.main-title-text', 
    'h1',
    '.title'
]})
```

### **3. Not Testing Selectors**
Always test your selectors with real data to ensure they work correctly!

---

## 🎯 **Summary**

- **Use selectors**: HTML, XML, YAML, CSV, Markdown validators
- **Don't use selectors**: JSON validators (use aliases instead)  
- **Provide fallbacks**: For robust extraction
- **Test thoroughly**: With real document samples
- **Leverage AI**: For natural language and auto-correction
