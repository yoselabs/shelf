# static-page-check

**Keep a no-build static web page honest.** A page made of plain ES modules, CSS, HTML and a few vendored
files has no bundler to catch a typo, a stray CDN link or a hard-coded colour. These checks do, as plain
functions: each returns a list of problem strings, and an empty list means fine. No test framework is
imported, so a consumer's test is one line.

```python
from pathlib import Path
from static_page_check import budget_problems, colour_problems, import_problems, page_problems, pin_problems

STATIC = Path("src/app/static")
VENDOR = ("vendor/ui-runtime.js",)

def test_static_page(self):
    self.assertEqual(import_problems(STATIC, vendored=VENDOR), [])
    self.assertEqual(page_problems(STATIC), [])
    self.assertEqual(pin_problems(STATIC, {"vendor/ui-runtime.js": "72284e8e..."}), [])
    self.assertEqual(colour_problems(STATIC, "css/tokens.css", vendored=VENDOR), [])
    self.assertEqual(budget_problems(STATIC, 100 * 1024), [])
```

- `import_problems`: every relative `import` resolves to a file and every `{named}` import is exported by its
  target (a vendored bundle only has to contain the name). Bare and absolute (CDN) imports are refused.
- `page_problems`: every `href`/`src` in an `.html` file is a relative URL to a file that exists.
- `pin_problems`: each vendored file hashes to its pinned sha256.
- `colour_problems`: `#hex`, `rgb(a)(` and `hsl(a)(` appear only in the tokens file. CSS comments, CSS id
  selectors and `href="#anchor"` are not colours. In JS a string such as `'#abc'` counts as one.
- `budget_problems`: all `.js` and `.css` together, gzipped at level 9, stay within a byte budget.

Paths inside `static_dir` are given relative to it (an absolute path also works). A `static_dir` that is not
a directory is itself a problem, so a wrong path never passes silently.

## Boundary

Imports no consumer app (`a2web`, `a2kay`) — enforced by `tests/test_boundary_static_page_check.py`.
