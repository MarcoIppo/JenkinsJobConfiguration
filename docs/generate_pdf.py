#!/usr/bin/env python3
"""Generate PDF from UserGuide markdown with custom cover page."""
import subprocess, sys, os

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(DOCS_DIR)

def generate_pdf(md_file, pdf_file, lang="en"):
    """Generate PDF with cover page and TOC."""
    
    # Titles by language
    if lang == "it":
        cover_title = "Jenkins Job Configuration Tool"
        cover_sub = "Guida Utente"
        cover_desc = "Creazione, manutenzione e versionamento delle<br/>configurazioni Jenkins Job tramite repository Git/Gerrit"
        toc_title = "Indice dei Contenuti"
    else:
        cover_title = "Jenkins Job Configuration Tool"
        cover_sub = "User Guide"
        cover_desc = "Create, maintain, and version-control Jenkins Job<br/>configurations using a local Git/Gerrit repository"
        toc_title = "Table of Contents"

    # Step 1: pandoc MD → HTML body with TOC
    pandoc_cmd = [
        "pandoc", md_file,
        "--from=markdown",
        "--to=html5",
        "--toc", "--toc-depth=2",
        "--resource-path=.:..",
        "--embed-resources",
    ]
    result = subprocess.run(pandoc_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Pandoc error: {result.stderr}")
        sys.exit(1)
    
    body_html = result.stdout

    # Step 2: Wrap with cover page
    css_path = os.path.join(DOCS_DIR, "pdf_style_v2.css")
    with open(css_path, "r") as f:
        css = f.read()

    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
{css}
</style>
</head>
<body>

<!-- COVER PAGE -->
<div class="cover">
  <img src="../multimedia/hydra_d.png" width="90"/>
  <h1>{cover_title}</h1>
  <div class="subtitle">{cover_sub}</div>
  <div class="version">ver. 1.0.0</div>
  <p style="color: #a0d4ff; font-size: 11pt;">{cover_desc}</p>
  <div class="footer-info">
    <img src="../multimedia/elogo.png" width="50"/><br/><br/>
    Ericsson Internal — 2026
  </div>
</div>

<!-- CONTENT -->
{body_html}

</body>
</html>"""

    # Step 3: Write temp HTML
    tmp_html = pdf_file.replace(".pdf", "_tmp.html")
    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(full_html)
    
    # Step 4: weasyprint → PDF
    subprocess.run(["weasyprint", tmp_html, pdf_file], check=True)
    
    # Cleanup
    os.remove(tmp_html)
    print(f"✓ Generated: {pdf_file}")


if __name__ == "__main__":
    generate_pdf("UserGuide.md", "UserGuide_EN.pdf", lang="en")
    if os.path.exists("UserGuide_IT.md"):
        generate_pdf("UserGuide_IT.md", "UserGuide_IT.pdf", lang="it")
