# Validation

Lamia validates LLM/Web/File responses automatically when you specify return types. Validators ensure outputs meet format and quality requirements before your code uses them.

## Built-in Validators

### File Format Validators

| Type | Description |
|------|-------------|
| `HTML` | Well-formed HTML |
| `JSON` | Valid JSON |
| `YAML` | Valid YAML |
| `XML` | Valid XML |
| `Markdown` | Valid Markdown |
| `CSV` | Valid CSV |

### File Structure Validators

Validate file format AND match a Pydantic model schema:

```python

class UserProfile(BaseModel):
    name: str
    age: int
    email: str

# In .lm files — validates JSON structure matches the model
def get_user() -> JSON[UserProfile]:
    "Generate a user profile"

```

Lamia's validation can be used in python code as well with:

```python
result = lamia.run("Generate a user profile", JSON[UserProfile])
```

Available structure validators: `JSON[Model]`, `YAML[Model]`, `XML[Model]`, `HTML[Model]`, `Markdown[Model]`, `CSV[Model]`

## Strict vs Permissive Mode

Each validator supports a `strict` flag (default: `true`):

- **`strict: true`**: Only accepts pure, valid output (no extra text around it)
- **`strict: false`**: Accepts output that contains a valid block within a longer response

When you want to be explicit about validation mode you can define file structure validators with `JSON[Model, True/False]`, `YAML[Model, True/False]`, `XML[Model, True/False]`, `HTML[Model, True/False]`, `Markdown[Model, True/False]`, `CSV[Model, True/False]`

Here is what strictness does for each case:

| Syntax                 | Model   | Strict | What happens                                              |
| ---------------------- | ------- | ------ | --------------------------------------------------------- |
| `HTML`                 | None    | True   | Plain HTML validation (well-formedness only), strict mode |
| `HTML[MyModel]`        | MyModel | False  | Structure validation against model, non-strict (default!) |
| `HTML[MyModel, True]`  | MyModel | True   | Structure validation against model, strict mode. Strict nesting is enforced           |
| `HTML[MyModel, False]` | MyModel | False  | Structure validation against model, explicitly non-strict. Any level of nesting |


## File Structure Validation

We will consider examples with HTML files, but the same principles apply to other file types.

## HTML Structure Validation for HTML generation

The following Lamia code will generate an HTML file with the structure defined in the `HtmlStructure` model and save it to the `output.html` file.

```python
class Body(BaseModel):
    h1: str
    p: str
    p: str

class HtmlStructure(BaseModel):
    title: str
    body: Body

"Generate a blog post about the benefits of using AI" -> File(HTML[HtmlStructure, True], "output.html") # The True in HTML[HtmlStructure, True] flag means no additional nestings are allowed, the document should have the same nestings as defined in the model
```

When tried with Claude Sonnet 4, the output was 

```html
<html>
<title>The Transformative Benefits of Using AI in Modern Life</title>
<body>
  <h1>The Transformative Benefits of Using AI in Modern Life</h1>
  <p>Artificial Intelligence has revolutionized how we work, learn, and solve problems in today's digital age. From automating repetitive tasks to providing intelligent insights from vast amounts of data, AI empowers individuals and organizations to achieve more with less effort. It enhances decision-making through predictive analytics, personalizes user experiences across platforms, and accelerates innovation in fields ranging from healthcare to education. By augmenting human capabilities rather than replacing them, AI serves as a powerful tool that frees us to focus on creative and strategic work while handling the mundane. As AI technology continues to evolve, its accessibility and applications expand, making it an indispensable asset for anyone looking to stay competitive and efficient in an increasingly complex world.</p>
</body>
</html>
```

This example script shows how you can use Lamia to generate HTML files with a desired structure all the time.

## HTML Structure Validation for HTML parsing

You can use HTML structure validation to parse HTML files to Pydantic models and use the model as you wish in your code. If the HTML structure is not as expected, the validation will fail and the rest of the code will not be executed. Validation makes sure that you extract the right data. When validation stops working, that might be a sign that the HTML structure has changed and you need to update the model.

Here is an example of simple web parsing with Lamia:

```python
class Body(BaseModel):
    h1: str

class HtmlStructure(BaseModel):
    title: str
    body: Body

website_content = "https://example.com" -> HTML[HtmlStructure]
if website_content.body.h1 == website_content.title:
    print("Example.com website header is the same as the title: h1: {website_content.body.h1}, title: {website_content.title}")
```

If you open the page source of the https://example.com, you will see, at the time of writing this, the HTML structure is like this:
```html
<html>
    <head>
        <title>Example.com</title>
    </head>
    <body>
      <div>
        <h1>Example.com</h1>
      </div>
    </body>
    ...
</html> ```

As you can see, as expected, the title is nested inside the <head> tag. Additionally, the <h1> tag is not nested inside the <body> tag. But the validation will succeed because the HTML structure is valid and we use `HTML[HtmlStructure]` in non-strict mode, which is why validation passes.

For parsing, usually the non-strict mode will be used. Otherwise, extensive Pydantic nested models might be needed to parse the HTML structure.

This is a useful, but simple example. Of course, in many real-world scenarios you will want to validate or extract complex HTML structures and using nested types to define them might be exhausting. That is why Lamia provides multiple additional ways to validate and extract data from the HTML structure. For example, you can use selectors to extract data from the HTML structure.

## Selector Usage with Validators

For details on using selectors within file type validators, see the [Selector Usage Guide](../validation/selector-usage-guide.md).