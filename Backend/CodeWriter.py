from dotenv import dotenv_values
from rich import print
from groq import Groq
import subprocess
import os

# ── Constants ──────────────────────────────────────────────────────────────────
GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "You are an expert software engineer and coding assistant. "
    "When given a coding task:\n"
    "1. Write clean, well-commented, production-ready code.\n"
    "2. Add a brief explanation at the top as a comment block.\n"
    "3. Include example usage at the bottom as comments.\n"
    "4. Always mention which language/framework is used.\n"
    "Respond with code only — no markdown fences, no extra prose outside of comments."
)

# ── Internal: Call Groq API ────────────────────────────────────────────────────
def _ask_groq(prompt: str) -> str:
    """Send a prompt to Groq and return the response text."""

    env_vars   = dotenv_values(".env")
    GroqAPIKey = env_vars.get("GroqAPIKey", "").strip()

    if not GroqAPIKey:
        return "Error: GroqAPIKey not found in .env file."

    try:
        client = Groq(api_key=GroqAPIKey)

        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=4096,
            temperature=0.7,
            top_p=1,
            stream=False,
            stop=None,
        )

        return completion.choices[0].message.content.strip()

    except Exception as e:
        return f"Error: {str(e)}"


# ── Internal: Clean markdown fences ───────────────────────────────────────────
def _clean_code(code: str) -> str:
    """Remove ```python or ``` fences if Groq adds them."""
    if code.startswith("```"):
        lines = code.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        code  = "\n".join(lines).strip()
    return code


# ── Internal: Detect file extension from code ─────────────────────────────────
def _detect_extension(code: str) -> str:
    """Guess file extension based on code content."""
    c = code.lower()
    if "def " in c or ("import " in c and "print(" in c):
        return ".py"
    elif "function " in c or "const " in c or "console.log" in c:
        return ".js"
    elif "<html" in c or "<!doctype" in c:
        return ".html"
    elif "public class " in c or "system.out" in c:
        return ".java"
    elif "#include" in c:
        return ".cpp"
    elif "select " in c and "from " in c:
        return ".sql"
    else:
        return ".py"  # default to python


# ── Internal: Open file in VS Code or Notepad ─────────────────────────────────
def _open_file(filepath: str) -> None:
    """Try VS Code first, fall back to Notepad."""
    username = os.environ.get("USERNAME", "")
    vscode_paths = [
        rf"C:\Users\{username}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        r"C:\Program Files\Microsoft VS Code\Code.exe",
        r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
    ]
    for path in vscode_paths:
        if os.path.exists(path):
            subprocess.Popen([path, filepath])
            return
    # Fallback to Notepad
    subprocess.Popen(["notepad.exe", filepath])


# ── PUBLIC FUNCTION: WriteCode ─────────────────────────────────────────────────
def WriteCode(topic: str) -> bool:
    """
    Code likhta hai Groq API se aur VS Code / Notepad mein open karta hai.

    Usage:
        WriteCode("snake game in python")
        WriteCode("REST API in Node.js")
        WriteCode("binary search in Java")
    """
    clean_topic = (
        topic.replace("write code for", "")
             .replace("write code", "")
             .replace("code for", "")
             .replace("WriteCode", "")
             .replace("create code", "")
             .strip()
    )

    if not clean_topic:
        print("[red]Error: Koi topic nahi diya code likhne ke liye.[/red]")
        return False

    print(f"[cyan]Writing code for:[/cyan] {clean_topic}")

    # ── Groq se code generate karo ────────────────────────────────────────
    code = _ask_groq(f"Write code for: {clean_topic}")

    if code.startswith("Error:"):
        print(f"[red]{code}[/red]")
        return False

    # ── Markdown fences clean karo ────────────────────────────────────────
    code = _clean_code(code)

    # ── File save karo ────────────────────────────────────────────────────
    os.makedirs(r"Data\Code", exist_ok=True)

    ext       = _detect_extension(code)
    safe_name = clean_topic.lower().replace(" ", "_")[:50]
    filepath  = rf"Data\Code\{safe_name}{ext}"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)

    print(f"[green]Code saved:[/green] {filepath}")

    # ── Editor mein open karo ─────────────────────────────────────────────
    _open_file(filepath)
    return True


# ── Quick test ─────────────────────────────────────────────────────────────────
# if __name__ == "__main__":
  #  WriteCode("Test")