# ForgeFile

ForgeFile is a small, custom scripting language and interpreter, powered by a
generic, grammar-driven lexer/parser engine called **Mono_py10**. You write
build/automation scripts in a file named `forgefile`, and the interpreter
(`ForgeFile.py`) reads a JSON grammar (`ForgeFileRule.json`), tokenizes and
parses your script into an intermediate representation (IR), and then
executes it.

Think of it as a tiny, hackable alternative to a Makefile — with variables,
shell commands, embedded Python, and user-defined functions — built on top of
a grammar engine that is itself fully reconfigurable via JSON.

---

## Project Structure

| File                | Purpose                                                                 |
|---------------------|--------------------------------------------------------------------------|
| `Mono_py10.py`      | Generic, JSON-grammar-driven lexer, tokenizer and normalizer (parser) engine |
| `ForgeFile.py`      | The ForgeFile interpreter — defines the runtime and executes the parsed IR |
| `ForgeFileRule.json`| The grammar definition (keywords, operators, symbols, parsing rules) for the ForgeFile language |
| `forgefile`         | Your script, written by you, placed in the current working directory   |

---

## How It Works

1. `Mono_py10.load_rule()` loads `ForgeFileRule.json`, which defines:
   - Keywords (`print`, `shell`, `func`, `call`, `py`, `let`, `notlet`, `eval`, ...)
   - Operators (`+ - * / = == != > < >= <=`)
   - Symbols (`( ) { } [ ] ; , :`)
   - Parsing rules — how each keyword's arguments are collected and what
     "action" they emit once a statement is complete.
2. `Lexer` turns the raw `forgefile` text into a token stream.
3. `Normalizer` walks the rule tree and turns tokens into a list of IR nodes,
   each shaped like:
   ```json
   { "action": "shell_cmd", "data": [...], "tab": 0, "line": 3, "col": 0 }
   ```
4. `ForgeFile.running_ir()` walks the IR and dispatches each action to a
   handler method (`shell_cmd`, `let_cmd`, `create_func`, etc.).

---

## Requirements

- Python 3.8+
- `Mono_py10.py` and `ForgeFileRule.json` must be located alongside (or one
  directory above) `ForgeFile.py`, as expected by the loader.
- No external dependencies — everything uses the Python standard library.

---

## Usage

```bash
python ForgeFile.py <function_name> [var1=value1 var2=value2 ...]
```

- `ForgeFile.py` looks for a file named `forgefile` in the **current working
  directory** and parses it.
- Any `key=value` arguments on the command line are injected into the
  variable scope before execution.
- Top-level statements in `forgefile` (e.g. `let`, `func` definitions) run
  immediately.
- If you pass one or more function names as arguments, ForgeFile will call
  them in sequence (each resolved function must have been defined with
  `func` in the script).

---

## Language Reference

Every statement in a `forgefile` script ends with a newline. Comments and
blocks are handled by the grammar/lexer, not documented as language keywords
below since they follow standard `//` / `/* */` conventions supported by the
lexer.

### `let <name> = <text>`
Assigns a variable. The right-hand side is treated as raw text with `$$name`
variable interpolation applied (see below) — **not** evaluated as an
expression.

```
let greeting = Hello $$user
```

### `notlet <name> = <text>`
Same as `let`, but only assigns if the variable **doesn't already exist**.
Useful for setting defaults that CLI arguments can override.

```
notlet mode = release
```

### `eval <name> = <expression>`
Assigns the result of a Python `eval()` on the right-hand side, using the
current variable scope as the evaluation namespace. Use this for real
arithmetic/logic, since `let` does no computation.

```
eval total = 1 + 2 * 3
```

> ⚠️ This runs raw Python `eval()` against your variable dictionary. Treat
> `forgefile` scripts as trusted code — do not run untrusted scripts.

### `shell <command>`
Runs a shell command via `os.system`, after interpolating `$$variables`.

```
shell echo Building $$mode version...
```

Prefix the command with `try` (or `_try`) to suppress/catch errors instead
of letting them propagate:

```
shell try rm -rf build
```

### `py <python code>`
Executes raw Python code with `exec()`, using the current variable scope as
globals — so assignments inside the block become script variables.

```
py print("running from embedded python")
```

> ⚠️ Same caveat as `eval` — this executes arbitrary Python code.

### `func <name> { <statements> }`
Defines a reusable block of ForgeFile statements under `name`. The body is
parsed as a nested code block (its own sub-IR) and stored, not executed
immediately.

```
func build {
    shell echo Compiling...
    let status = done
}
```

### `call <name>`
Invokes a previously defined `func` block. It runs in a child interpreter
that shares (and can mutate) the parent's variable scope.

```
call build
```

### `print <text>`
Recognized by the grammar (tokenized into a `print_cmd` action), but **note:
the interpreter does not currently implement a handler for it** — `print_cmd`
is not registered in `ForgeFile.mapping_function`, so `print` statements are
parsed but silently produce no output. Use `shell echo ...` or `py print(...)`
instead until this is wired up.

---

## Variable Interpolation

Inside `let`, `notlet`, and `shell` arguments, any whitespace-separated token
starting with `$$` is replaced with the value of the matching variable (if it
exists):

```
let name = World
shell echo Hello $$name
```

Interpolation is done by simple whitespace-token replacement (`calc_var_string`),
not full string-embedded substitution — so `$$name` must be its own
space-separated token to be recognized.

---

## Example `forgefile`

```
notlet mode = debug

let message = Starting build in $$mode mode

func build {
    shell echo $$message
    eval version = 1 + 1
    shell echo Build version is $$version
}

call build
```

Run it:

```bash
python ForgeFile.py
```

Or override the default mode and call a function from the CLI:

```bash
python ForgeFile.py build mode=release
```

---

## The Mono_py10 Grammar Engine

`Mono_py10.py` is not tied to ForgeFile specifically — it's a general-purpose
toolkit for building small DSLs from a JSON grammar file. `ForgeFileRule.json`
is just one such grammar. Key building blocks:

- **`lexer.keyword` / `lexer.operator` / `lexer.symbol`** — define which raw
  strings become which token types.
- **`rules`** — a tree per starting keyword describing how to consume
  subsequent tokens (via `collect*` modes) until an `"end"` marker emits an
  action name.
- **`normalizer.collect_types`** — whitelist of token types allowed inside
  each `collect*` mode (e.g. `collectint` only allows `INT` tokens).
- **`normalizer.collect_brackets`** — which open/close token types (or custom
  characters) bound a `collect*` mode (e.g. `collectlist` uses `[` `]`).
- **`normalizer.collect_delimiters`** — item/key-value separators for lists
  and maps.
- **`normalizer.collect_string_modes`** — define custom string literal
  syntax (e.g. `##...##`) with custom escape sequences.
- **`normalizer.collect_expr_mode`** — which collect modes should use the
  expression-aware collector (supports parentheses and operators).
- **`_error_policy`** — per error type (`unknown_token`, `type_error`,
  `unclosed_bracket`, `unclosed_string`, `invalid_char`, `unknown_operator`,
  `rule_not_matched`, `schema_violation`), choose `"exit"` to raise/stop or
  `"warn"` to print a warning and continue.

You can define your own DSL entirely by writing a new `rule.json` and calling
`Mono_py10.load_rule("your_rule.json")` before lexing/parsing — no engine
code changes required. `Mono_py10.create_rule_template("myrule")` will
scaffold a starter grammar file for you.

---

## Error Handling

Runtime errors raised while executing IR nodes are caught in
`ForgeFile.running_ir()`, printed as:

```
[ERROR] <message> in <line>:<col>
```

and the process exits with status code `1`. Parser/lexer-level errors are
governed by the `_error_policy` block in `ForgeFileRule.json`.

---

## Known Limitations

- `print` is defined in the grammar but has no execution handler — statements
  parse successfully but produce no runtime effect.
- `eval` and `py` execute arbitrary Python against the live variable scope —
  only run trusted scripts.
- Variable interpolation (`$$var`) only matches whole whitespace-delimited
  tokens, not substrings within a larger token.
- `debug` / `debug_ir` flags at the top of `ForgeFile.py` are hardcoded
  (`False`) — flip them manually for tracing/debug output.

---

## License

No license specified — add one appropriate for your project before
distributing.# ForgeFile-v1
# ForgeFile
