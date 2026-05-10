# Getting Started with Lamia

This guide walks you through writing your first Lamia programs — from a single-file script to a multi-file project with shared models and reusable prompts.

## Setting up a project

Start by creating a project folder and initializing it:

```bash
mkdir my-lamia-project
cd my-lamia-project
lamia init
```

`lamia init` creates a `config.yaml` with your model chain and a `.env` file for API keys. Follow the prompts to select your LLM provider and enter your API key.

Your project now looks like this:

```
my-lamia-project/
├── config.yaml
└── .env
```

## Your first program: a single .lm file

Create a file called `hello.lm`:

```python
def greet():
    "Write a short, friendly greeting for a new Lamia user"

result = greet()
print(result)
```

Run it:

```bash
lamia hello.lm
```

That's it. The string inside `greet()` is sent to the LLM configured in your `config.yaml`, and the response is printed.

### Adding a return type

Without a return type, you get raw text. Add `-> HTML` to validate and extract HTML:

```python
def generate_page() -> HTML:
    "Create a simple HTML page that says Welcome to Lamia"

page = generate_page()
print(page)
```

Or get structured data with a Pydantic model:

```python

class Greeting(BaseModel):
    message: str = Field(description="The greeting text")
    language: str = Field(description="Language code, e.g. en, es, de")

def greet() -> JSON[Greeting]:
    "Write a friendly greeting and identify the language"

result = greet()
print(f"{result.message} (language: {result.language})")
```

Save output to a file with `-> File(...)`:

```python
"Create a simple landing page" -> File(HTML, "landing.html")
```

## Extracting prompts into .hu files

As your prompts grow, you will want to separate them from your logic. `.hu` (human) files are plain-text prompt templates — they contain just the prompt, with optional parameters.

Create `summarize.hu`:

```
Summarize the following text in {max_words} words or fewer:

{text}
```

Now create `pipeline.lm` to call it:

```python
article = """
Lamia is a scripting language that combines Python syntax with LLM commands,
file operations, and web automation. It uses .lm files for logic and .hu files
for prompt templates.
"""

result = summarize(text=article, max_words=30)
print(result)
```

Run it:

```bash
lamia pipeline.lm
```

Lamia automatically discovers `summarize.hu` and makes it callable as a function. The filename (without `.hu`) becomes the function name.

### Multiple .hu files from one .lm file

A single `.lm` file can call as many `.hu` files as needed:

Create `translate.hu`:

```
Translate the following text to {language}:

{text}
```

Update `pipeline.lm`:

```python
article = """
Lamia is a scripting language that combines Python syntax with LLM commands.
"""

summary = summarize(text=article, max_words=30)
spanish = translate(text=summary, language="Spanish")
print(f"Summary: {summary}")
print(f"Spanish: {spanish}")
```

## A real multi-file workflow: analyze then trade

This is a realistic split where each `.lm` file owns a separate workflow:

- `report.lm` defines functions to gather market data and write a structured analyst report.
- `buy_stocks.lm` defines functions to read that report and place the buy order for the winner.
- `orchestrator.lm` calls these functions directly — Lamia auto-discovers them from neighboring files.

Create `analyst_report.hu`:

```
You are a financial analyst.
Using the stock table below, rank symbols by short-term opportunity.
Return:
- winner: top symbol to buy now
- runner_up: second choice
- rationale: short explanation for both
- risk_note: key risk to monitor

Stock data:
{@stocks.csv}
```

Create `report.lm`:

```python
def stock_data(ticker: str) -> File(CSV[StockQuote], "stocks.csv", append=True):
    "extract quote summary from https://finance.yahoo.com/quote/{ticker}"


def generate_report():
    tickers = ["AAPL", "NVDA", "MSFT", "GOOG"]
    for ticker in tickers:
        stock_data(ticker=ticker)
        print(f"Scraped {ticker}")

    with files("./"):
        analyst_report() -> File(JSON[AnalystReport], "analyst_report.json")

    print("Created stocks.csv and analyst_report.json")
```

Create `buy_stocks.lm`:

```python
def submit_order(order: BuyOrder) -> str:
    """Submit order via broker website automation with persistent session."""
    
    # Login only once - session persists across calls
    with session("broker_login"):
        web.navigate("https://broker.example.com/login")
        web.type_text("Username input field", os.getenv("BROKER_USERNAME"))
        web.type_text("Password input field", os.getenv("BROKER_PASSWORD"))
        web.click("Login button")
        web.wait_for("Dashboard", "visible")
    
    # This runs every time - session block skipped if already logged in
    web.navigate("https://broker.example.com/trades")
    web.wait_for("Trade form", "visible")
    
    # Get portfolio balance
    balance_text = web.get_text("Portfolio balance")
    available_budget = float(balance_text.replace("$", "").replace(",", ""))
    
    # Use minimum of requested budget or available budget
    actual_budget = min(order.budget_usd, available_budget)
    
    # Search for ticker
    web.type_text("Symbol search input", order.symbol)
    web.click("Search button")
    web.wait_for(f"Symbol result for {order.symbol}", "visible")
    web.click(f"Symbol result for {order.symbol}")
    
    # Place order
    web.click("Buy order button")
    web.type_text("Amount input field", str(actual_budget))
    web.select_option("Order type dropdown", "market")
    web.click("Submit order button")
    web.wait_for("Order confirmation", "visible")
    
    # Get confirmation
    confirmation = web.get_text("Order confirmation message")
    
    if "success" in confirmation.lower():
        f"submitted: {order.symbol} for ${actual_budget}"
    else:
        f"failed: {confirmation}"


def buy_winner_stock(default_budget_usd: float = 1000.0):
    report = "./analyst_report.json" -> JSON[AnalystReport]
    winner = report["winner"]

    order = BuyOrder(symbol=winner, side="buy", budget_usd=default_budget_usd, order_type="market")
    status = submit_order(order)
    print(f"Order status: {status}")
```

Create `orchestrator.lm`:

```python
generate_report()
buy_winner_stock()
print("Pipeline complete: analysis generated and winner purchased")
```

Lamia auto-discovers `generate_report` from `report.lm` and `buy_winner_stock` from `buy_stocks.lm` — no imports or subprocess calls needed.

Run the full workflow:

```bash
lamia orchestrator.lm
```

## Sharing Pydantic models across files

When multiple `.lm` files need the same schemas, keep them in `models/schemas.py`:

```
stock-report/
├── config.yaml
├── .env
├── models/
│   └── schemas.py
├── analyst_report.hu
├── report.lm
├── buy_stocks.lm
└── orchestrator.lm
```

`models/schemas.py`:

```python

class StockQuote(BaseModel):
    ticker: str = Field(description="Stock ticker symbol, e.g. AAPL")
    open: float = Field(description="Open price from the quote summary section")
    bid: str = Field(description="Bid price and size")
    ask: str = Field(description="Ask price and size")


class AnalystReport(BaseModel):
    winner: str = Field(description="Top symbol to buy")
    runner_up: str = Field(description="Second-best symbol")
    rationale: str = Field(description="Why these symbols were selected")
    risk_note: str = Field(description="Main risk to watch")


class BuyOrder(BaseModel):
    symbol: str = Field(description="Ticker to trade")
    side: str = Field(description="buy or sell")
    budget_usd: float = Field(gt=0, description="Dollar amount to deploy")
    order_type: str = Field(description="market or limit")
```

Any `.lm` file can import these models with standard Python imports.

## Using Lamia Studio

If you prefer a visual environment, [Lamia Studio](https://github.com/lamia-lang/lamia-ide) is a lightweight IDE built for Lamia. It includes a chat interface that can write Lamia programs for you — describe what you want in plain language and the chat generates `.lm` and `.hu` files.

Install it from the [releases page](https://github.com/lamia-lang/lamia-ide/releases/latest).

## What to read next

These guides cover the full language features in depth:

1. **[.hu File Syntax](../user-guide/hu-syntax.md)** — parameter placeholders, file context references, default values, and calling conventions for prompt templates.

2. **[.lm File Syntax](../user-guide/lm-syntax.md)** — return types, model selection, variable substitution, file operations, session management, web automation, and async execution.

3. **[Web Automation](../user-guide/web-automation.md)** — browser control, form filling, screenshots, and scoped element operations.

4. **[File Context](../user-guide/files-context.md)** — referencing local files (PDFs, CSVs, code) in your prompts with `{@filename}` syntax.

5. **[Using Lamia in Python](python-library.md)** — call Lamia from your Python apps and scripts instead of running `.lm` files from the CLI.