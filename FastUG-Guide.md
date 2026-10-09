# FastUG User Guide

FastUG turns a user guide written in short commands into a finished Markdown file, ready to preview and export to PDF. You write `\"icon:Settings"\` and FastUG replaces it with the full `<img>` tag. Boxes, buttons, diagrams and reusable text blocks work the same way.

---

## 1. What you need

- **Python 3.** The main script only uses the standard library, so there is nothing to install.
- **VS Code** with the **Markdown Preview Enhanced** extension, to preview and export the result.
- *(Optional)* **PyMuPDF** (`pip install pymupdf`), only if you want page numbers in the table of contents.

## 2. Project layout

| Path | What it is |
|---|---|
| `userguide.md` | The user guide you write. |
| `template.md` | Reusable text blocks ("sections") you can insert anywhere. |
| `commands.md` | Your own custom commands (see section 6). |
| `Icons/` | Small inline images (`.png`). |
| `Diagrams/` | Screenshots and diagrams (`.png`). |
| `styles.css` | Styles for the exported HTML/PDF. |
| `.crossnote/style.less` | The same styles for the VS Code live preview. |
| `script/` | The FastUG scripts, settings and config files. |

FastUG creates these files. **Never edit them by hand**, because the next run overwrites them:

- `userguide_res.md`, `template_res.md`: the expanded output.
- `script/Configs/icons.json`, `diagrams.json`, `template.json`, `custom.json`.
- `userguide.html`, `userguide.pdf`: the exports from Markdown Preview Enhanced.

## 3. Quick start

From the project folder, run:

```
python script/script.py 1
```

This runs **Quick Start**, which does every step in the right order. Your result is written to `userguide_res.md`. Your original `userguide.md` is not changed.

Next, open `userguide_res.md` in VS Code, preview it with Markdown Preview Enhanced and export it to PDF.

### The individual steps

Pass a number to run a single step. If you leave the number out, a menu asks you which step to run.

| # | Step | What it does |
|---|---|---|
| 1 | Quick Start | Runs steps 2–5 in order. |
| 2 | Load Picture JSON | Indexes every `.png` in `Icons/` and `Diagrams/`. |
| 3 | Replace & Load Template | Expands `template.md` and loads its sections. |
| 4 | Replace & Load Commands | Loads your custom commands from `commands.md`. |
| 5 | Replace Userguide | Expands `userguide.md` into `userguide_res.md`. |

**If you're not sure which step to run, run Quick Start.** It's always safe to use.

## 4. Writing commands

Every command uses the same pattern:

```
\"name:field1:field2"\
```

- It **starts** with `\"` and **ends** with `"\` (a quote, then a backslash).
- Fields are separated by colons `:`.
- Ordinary quotes in your text (without the backslash) are left alone.

### Built-in commands

| Command | Example | Result |
|---|---|---|
| `icon` | `\"icon:Settings"\` | Inline icon from `Icons/` |
| `diagram` | `\"diagram:Profile Page:80"\` | Diagram from `Diagrams/` at 80% width |
| `template` | `\"template:Save Changes"\` | Inserts a section from `template.md` |
| `box` | `\"box:tip:Good to know:Body text"\` | Callout box: `tip`, `warn` or `danger` |
| `ui` | `\"ui:primary:Save"\` | App button with text |
| `uisvg` | `\"uisvg:primary:refresh:Refresh"\` | App button with an icon and text |
| `uiicon` | `\"uiicon:primary:more-options"\` | App button with an icon only |

**Button styles:** `primary`, `old`, `gray-old`, `green-old`, `blue-old`, `sidemenu-category`, `sidemenu-option`.

**Button icons:** `refresh`, `filter`, `more-options`, `add`, `export`, `delete`, `cancel`, `check`, `copy`. Every icon is a `.svg-{name}` rule in `styles.css`, so check there for the full list.

### Image names

An image's name is its filename without `.png`, with the CamelCase split into words:

- `Icons/SettingsIcon.png` → `\"icon:Settings Icon"\`
- `Diagrams/ProfilePage.png` → `\"diagram:Profile Page:80"\`

To add an image, drop the `.png` into `Icons/` or `Diagrams/` and run Quick Start (or step 2).

### Nesting commands

You can put commands inside the **last** field of another command, for example an icon inside a box:

```
\"box:tip:Good to know:Click \"icon:Settings"\ to change your preferences."\
```

**Only the last field can contain colons.** Don't nest commands in a box's type or title.

### Snippets

Type a command name such as `box` or `ui` in VS Code and the snippet autocompletes it. Press Tab to move from one field to the next.

## 5. Templates (`template.md`)

Put text you repeat often into `template.md` as a named section:

```
\"section:Save Changes:1) Click Save to keep your changes."\
```

Insert it anywhere in your guide with `\"template:Save Changes"\`. Sections can contain other commands such as icons, boxes and buttons. **Don't put custom commands inside a section** (see section 6). Instead, place them in `userguide.md` next to the template call.

## 6. Custom commands (`commands.md`)

Custom commands are reusable blocks with blanks to fill in. Define each one in `commands.md` between `!"` and `"!`, and mark each blank with `\"field:Name"\`:

```
!"command:Open Profile:
1) Go to the \"field:Tab"\ on your profile page.
1) Click \"field:Button"\.
"!
```

After you run Quick Start (or step 4), use the command like this:

```
\"custom:Open Profile:Information Tab:Open"\
```

This fills `Tab` with "Information Tab" and `Button` with "Open". The snippet `custom:Open Profile` autocompletes the fields for you.

Rules for custom commands:

- **Give every field, in the order it first appears in the definition.** If you give too few fields, FastUG doesn't show an error. It silently swallows text up to some later `"\` in the document.
- A field that isn't the last one can't contain a colon. If it needs one (for example a nested `\"icon:…"\`), wrap the field in `$( … )$`:

  ```
  \"custom:Open Profile:$(Information \"icon:Settings"\ Tab)$:Open"\
  ```

## 7. Table of contents

Put `[TOC]` where you want the table of contents. After Replace Userguide, run:

```
python script/generate_toc.py
```

This replaces `[TOC]` in `userguide_res.md` with a numbered table of contents. To add page numbers:

1. Export `userguide_res.md` to PDF.
2. Run `python script/generate_toc.py --pdf userguide.pdf`.
3. Export again. Re-run step 2 until it reports a shift of `0`.

Re-run `generate_toc.py` every time you run Replace Userguide, because Replace Userguide resets the table of contents.

## 8. Formatting tips

- **Leave a blank line after every box or table.** Otherwise the lines that follow render as plain text.
- **Inside a box, use HTML instead of Markdown**: `<ul><li>…</li></ul>` instead of `- `, and `<b>` instead of `**`.
- **Indent nested list items by 4 spaces.**
- **To put an image on its own line** directly under a sentence, put a line containing only `\` before it.
- **To start a new page**, add `<div class="page-break"></div>` with a blank line on each side.

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `Error: File 'X' not found for command 'Y'` in the output | Name typo, or the image or section is missing. Check the spelling, then run Quick Start. |
| A large chunk of the guide disappears or gets mixed up | A custom command was given the wrong number of fields. Compare the call with its definition in `commands.md`. |
| A command shows up as raw text | Check it ends with `"\`, not just `"`. |
| A button icon is invisible | The icon name is misspelt. Use one from the list in section 4. |
| The font looks like Arial | The Inter font loads from Google Fonts, so you need an internet connection when you export. |
| The script stops before running | A file or folder in `script/settings.json` is missing. The error message names it. |

Details of each run are written to `script/script.log`.

## 10. Settings

You can change file and folder names in `script/settings.json`, for example:

```json
{
    "userguide_path": "userguide.md",
    "template_path": "template.md",
    "command_path": "commands.md",
    "icon_dir": "Icons/",
    "diagram_dir": "Diagrams/",
    "compiled_suffix": "_res"
}
```

**Leave the folder names and `compiled_suffix` as they are.** Some of the steps still use the default names, so changing them makes the steps read and write different files.
